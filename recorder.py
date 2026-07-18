"""
Gravação de tela e áudio via FFmpeg (subprocess).
Suporta captura de uma ou várias telas e mixagem de vários microfones.
"""

import subprocess
import os
import sys
import time
import threading
from datetime import datetime
from config import get_ffmpeg_path, Config
from audio_capture import SystemAudioCapture


class Recorder:
    def __init__(self, config: Config):
        self.config = config
        self.process = None
        self.is_recording = False
        self.is_paused = False
        self.start_time = None
        self.pause_time = None
        self.total_paused = 0
        self._lock = threading.Lock()
        self._output_path = None

    def get_ffmpeg(self):
        path = get_ffmpeg_path()
        if not path:
            raise FileNotFoundError(
                "FFmpeg não encontrado. Verifique a instalação."
            )
        return path

    def get_output_path(self):
        folder = self.config.get("output_folder")
        os.makedirs(folder, exist_ok=True)
        fmt = self.config.get("format", "mp4")
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"gravacao_{timestamp}.{fmt}"
        return os.path.join(folder, filename)

    # ------------------------------------------------------------------
    # Helpers de codificação / áudio
    # ------------------------------------------------------------------
    def _quality_crf(self):
        quality = self.config.get("quality", "high")
        return {"low": "28", "medium": "23", "high": "18", "ultra": "15"}.get(quality, "18")

    def _vcodec(self):
        return "libx264" if self.config.get("codec", "h264") == "h264" else "libx265"

    # Nomes (em minúsculas) que identificam um dispositivo de "loopback"
    # (som do sistema/saída). O usuário precisa ter um destes habilitado.
    LOOPBACK_MARKERS = (
        "virtual-audio-capturer", "stereo mix", "mixagem est",
        "what u hear", "what you hear", "cable output",
        "voicemeeter out", "wave out mix", "loopback",
    )

    @staticmethod
    def _find_loopback_device(devices):
        """Retorna o primeiro dispositivo de saída/loopback encontrado, ou None."""
        for d in devices:
            low = d.lower()
            if any(m in low for m in Recorder.LOOPBACK_MARKERS):
                return d
        return None

    def _pick_mic(self, devices, loopback):
        """Escolhe o microfone a usar (o configurado, ou o 1º que não é loopback)."""
        chosen = self.config.get("audio_device", "auto")
        if chosen and chosen not in ("auto", "all", "todos", "default"):
            if chosen in devices and chosen != loopback:
                return chosen
        for d in devices:
            if d != loopback:
                return d
        return None

    def _plan_audio(self):
        """
        Decide como capturar áudio segundo o 'audio_mode'. Retorna
        (dispositivos_ffmpeg, usar_python_sistema).

        - "system_mic": som do sistema + microfone
        - "system":     apenas o som do sistema
        - "mic":        apenas o microfone escolhido
        - "all":        todos os microfones detectados

        O som do SISTEMA é capturado preferencialmente via WASAPI loopback
        (Python, sem driver). Se indisponível, tenta um dispositivo de
        loopback do dshow (ex.: Mixagem Estéreo), se existir.
        """
        if not self.config.get("audio_enabled", True):
            return [], False

        devices = self.list_audio_devices()
        mode = self.config.get("audio_mode", "system_mic")

        if mode == "all":
            return devices, False

        loopback = self._find_loopback_device(devices)
        mic = self._pick_mic(devices, loopback)
        want_system = mode in ("system", "system_mic")
        want_mic = mode in ("mic", "system_mic")

        ff = []
        use_python = False

        if want_system:
            if SystemAudioCapture.available():
                use_python = True          # captura sistema via WASAPI (Python)
            elif loopback:
                ff.append(loopback)        # fallback: loopback via dshow

        if want_mic and mic:
            ff.append(mic)

        # Remove duplicados preservando ordem
        seen, out = set(), []
        for d in ff:
            if d not in seen:
                seen.add(d)
                out.append(d)
        ff = out

        # Fallback final: se não sobrou nada capturável, usa o microfone.
        if not ff and not use_python:
            if mic:
                ff.append(mic)
            elif devices:
                ff.append(devices[0])

        return ff, use_python

    def _append_output_encoding(self, cmd, output, n_audio):
        """Adiciona codecs, mapeamentos e o arquivo de saída ao comando."""
        fmt = self.config.get("format", "mp4")
        vcodec = self._vcodec()
        crf = self._quality_crf()

        # Mixagem de áudio quando há mais de um dispositivo
        if n_audio > 1:
            inputs = "".join(f"[{i + 1}:a]" for i in range(n_audio))
            cmd.extend([
                "-filter_complex",
                f"{inputs}amix=inputs={n_audio}:duration=longest:normalize=0[aout]",
            ])
            cmd.extend(["-map", "0:v", "-map", "[aout]"])
        elif n_audio == 1:
            cmd.extend(["-map", "0:v", "-map", "1:a"])
        else:
            cmd.extend(["-map", "0:v"])

        # Vídeo
        fps = self.config.get("fps", 30)
        cmd.extend([
            "-c:v", vcodec,
            "-crf", crf,
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            # Frame rate CONSTANTE na saída — corrige o engasgo do gdigrab
            # (que entrega frames irregulares -> reprodução travada).
            "-r", str(fps),
            "-fps_mode", "cfr",
        ])

        # MP4/MOV padrão e reproduzível em qualquer player (moov no início).
        if fmt in ("mp4", "mov"):
            cmd.extend(["-movflags", "+faststart"])

        # Áudio
        if n_audio >= 1:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])

        cmd.append(output)

    def _make_startupinfo(self):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        return startupinfo

    # ------------------------------------------------------------------
    # Montagem do comando
    # ------------------------------------------------------------------
    def build_command(self, monitor_indices, capture_all, audio_devices, output,
                      region=None):
        """
        Monta comando FFmpeg para gravação de tela(s).
        monitor_indices: lista de índices de monitores (0-based) ou None
        capture_all: True para capturar todas as telas juntas
        audio_devices: lista de dispositivos dshow a gravar (pode ser vazia)
        output: caminho do arquivo de saída
        region: (x, y, w, h) para gravar uma região específica (opcional)
        """
        ffmpeg = self.get_ffmpeg()
        fps = self.config.get("fps", 30)

        cmd = [ffmpeg, "-y"]

        # ---------- VÍDEO ----------
        # Região explícita (seleção manual) tem prioridade.
        if region is None and not capture_all and monitor_indices:
            try:
                from screeninfo import get_monitors
                monitors = get_monitors()
                selected = [monitors[i] for i in monitor_indices
                            if 0 <= i < len(monitors)]
                # Se selecionou todos, é o mesmo que desktop inteiro
                if selected and len(selected) < len(monitors):
                    region = self._bounding_region(selected)
            except Exception:
                region = None

        if region:
            x, y, w, h = region
            cmd.extend([
                "-thread_queue_size", "1024",
                "-f", "gdigrab",
                "-framerate", str(fps),
                "-offset_x", str(x),
                "-offset_y", str(y),
                "-video_size", f"{w}x{h}",
                "-i", "desktop",
            ])
        else:
            # Desktop inteiro (todas as telas)
            cmd.extend([
                "-thread_queue_size", "1024",
                "-f", "gdigrab",
                "-framerate", str(fps),
                "-i", "desktop",
            ])

        # ---------- ÁUDIO ----------
        for dev in audio_devices:
            cmd.extend([
                "-thread_queue_size", "1024",
                "-rtbufsize", "100M",
                "-f", "dshow",
                "-i", f"audio={dev}",
            ])

        # ---------- SAÍDA ----------
        self._append_output_encoding(cmd, output, len(audio_devices))
        return cmd

    @staticmethod
    def _bounding_region(monitors):
        """Calcula o retângulo que engloba os monitores selecionados (dims pares)."""
        x0 = min(m.x for m in monitors)
        y0 = min(m.y for m in monitors)
        x1 = max(m.x + m.width for m in monitors)
        y1 = max(m.y + m.height for m in monitors)
        w = (x1 - x0)
        h = (y1 - y0)
        # x264/yuv420p exige dimensões pares
        w -= w % 2
        h -= h % 2
        return (x0, y0, w, h)

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------
    @staticmethod
    def _log_path():
        d = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")), "VideoRecorder"
        )
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "ffmpeg.log")

    def _spawn(self, cmd, output):
        """Inicia o FFmpeg, gravando o stderr num log (arquivo não bloqueia)."""
        # stderr vai para um ARQUIVO (não pipe) — não trava e permite diagnóstico.
        self._log_fh = open(self._log_path(), "w", encoding="utf-8", errors="replace")
        self._log_fh.write("===== COMANDO FFMPEG =====\n")
        self._log_fh.write(" ".join(f'"{c}"' if " " in c else c for c in cmd))
        self._log_fh.write("\n\n===== SAÍDA DO FFMPEG =====\n")
        self._log_fh.flush()

        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=self._log_fh,
            startupinfo=self._make_startupinfo(),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.is_recording = True
        self.is_paused = False
        self.start_time = time.time()
        self.total_paused = 0
        self._output_path = output
        self._markers = []

    def _reset_audio_job(self):
        self._sys_capture = None
        self._sys_wav = None
        self._use_python_audio = False
        self._raw_output = None
        self._final_output = None
        self._raw_has_audio = False

    def start(self, monitor_indices=None, capture_all=False, region=None):
        """Inicia gravação de tela(s), com áudio conforme o modo configurado.

        region: (x, y, w, h) para gravar apenas uma região (opcional).
        """
        with self._lock:
            if self.is_recording:
                return None

            self._reset_audio_job()
            try:
                ff_devices, use_python = self._plan_audio()
            except Exception:
                ff_devices, use_python = [], False

            final_output = self.get_output_path()
            # Se vamos capturar o sistema via Python, o FFmpeg grava num
            # arquivo temporário e depois fazemos o mux (vídeo + áudios).
            raw_output = (final_output + ".video.mp4") if use_python else final_output

            try:
                cmd = self.build_command(monitor_indices, capture_all,
                                         ff_devices, raw_output, region=region)
            except FileNotFoundError as e:
                return str(e)

            # Inicia captura do som do sistema (WASAPI loopback), se aplicável.
            if use_python:
                self._sys_wav = final_output + ".sys.wav"
                cap = SystemAudioCapture()
                if cap.start(self._sys_wav):
                    self._sys_capture = cap
                else:
                    # Falhou em iniciar -> grava sem som do sistema.
                    use_python = False
                    raw_output = final_output
                    # Reconstrói o comando apontando para o arquivo final.
                    try:
                        cmd = self.build_command(monitor_indices, capture_all,
                                                 ff_devices, raw_output, region=region)
                    except FileNotFoundError as e:
                        return str(e)

            self._use_python_audio = use_python
            self._raw_output = raw_output
            self._final_output = final_output
            self._raw_has_audio = len(ff_devices) > 0

            try:
                self._spawn(cmd, final_output)
                return None
            except Exception as e:
                # aborta captura de sistema se o ffmpeg não subiu
                if self._sys_capture:
                    try:
                        self._sys_capture.stop()
                    except Exception:
                        pass
                    self._sys_capture = None
                return str(e)

    def start_window(self, window_title):
        """Inicia gravação de uma janela específica pelo título."""
        with self._lock:
            if self.is_recording:
                return None

            self._reset_audio_job()
            try:
                ff_devices, use_python = self._plan_audio()
            except Exception:
                ff_devices, use_python = [], False

            try:
                ffmpeg = self.get_ffmpeg()
                fps = self.config.get("fps", 30)
                final_output = self.get_output_path()
                raw_output = (final_output + ".video.mp4") if use_python else final_output

                def _build(devices, out):
                    c = [
                        ffmpeg, "-y",
                        "-thread_queue_size", "1024",
                        "-f", "gdigrab",
                        "-framerate", str(fps),
                        "-i", f"title={window_title}",
                    ]
                    for dev in devices:
                        c.extend([
                            "-thread_queue_size", "1024",
                            "-rtbufsize", "100M",
                            "-f", "dshow",
                            "-i", f"audio={dev}",
                        ])
                    self._append_output_encoding(c, out, len(devices))
                    return c

                cmd = _build(ff_devices, raw_output)

                if use_python:
                    self._sys_wav = final_output + ".sys.wav"
                    cap = SystemAudioCapture()
                    if cap.start(self._sys_wav):
                        self._sys_capture = cap
                    else:
                        use_python = False
                        raw_output = final_output
                        cmd = _build(ff_devices, raw_output)

                self._use_python_audio = use_python
                self._raw_output = raw_output
                self._final_output = final_output
                self._raw_has_audio = len(ff_devices) > 0

                self._spawn(cmd, final_output)
                return None
            except FileNotFoundError as e:
                return str(e)
            except Exception as e:
                if self._sys_capture:
                    try:
                        self._sys_capture.stop()
                    except Exception:
                        pass
                    self._sys_capture = None
                return str(e)

    def stop(self):
        """Para gravação e finaliza o arquivo de forma graciosa."""
        with self._lock:
            if not self.is_recording or not self.process:
                return None

            # 1. Pede finalização graciosa ao FFmpeg (escreve 'q' no stdin).
            #    Isso permite que o moov atom seja escrito -> vídeo reproduzível.
            try:
                if self.process.stdin:
                    self.process.stdin.write(b"q")
                    self.process.stdin.flush()
                    self.process.stdin.close()
            except Exception:
                pass

            # 2. Aguarda a finalização (gravações de tela finalizam rápido).
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                # 'q' não funcionou — encerra de forma controlada.
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except Exception:
                    try:
                        self.process.kill()
                        self.process.wait(timeout=3)
                    except Exception:
                        pass

            self.is_recording = False
            self.is_paused = False
            self.process = None

            # Fecha o log do ffmpeg
            try:
                if getattr(self, "_log_fh", None):
                    self._log_fh.close()
                    self._log_fh = None
            except Exception:
                pass

            # Finaliza captura do som do sistema e faz o mux, se aplicável.
            final = getattr(self, "_final_output", None) or self._output_path
            self._finalize_audio_job(final)
            self._write_markers(final)
            return final

    def add_marker(self, label=None):
        """Registra um marcador no instante atual da gravação."""
        if not self.is_recording:
            return None
        elapsed = self.get_elapsed()
        if not hasattr(self, "_markers"):
            self._markers = []
        n = len(self._markers) + 1
        marker = {"time": elapsed, "label": label or f"Marcador {n}"}
        self._markers.append(marker)
        return marker

    def get_markers(self):
        return list(getattr(self, "_markers", []))

    def _write_markers(self, final):
        markers = getattr(self, "_markers", None)
        if not markers or not final:
            return
        try:
            path = os.path.splitext(final)[0] + ".markers.txt"
            with open(path, "w", encoding="utf-8") as f:
                f.write("Marcadores da gravação\n")
                f.write("=" * 30 + "\n\n")
                for m in markers:
                    t = int(m["time"])
                    ts = f"{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}"
                    f.write(f"[{ts}]  {m['label']}\n")
        except Exception:
            pass

    def _finalize_audio_job(self, final):
        """Para a captura de sistema e combina vídeo + áudios no arquivo final."""
        if not getattr(self, "_use_python_audio", False):
            return  # nada a fazer: ffmpeg já gravou direto no arquivo final

        raw = getattr(self, "_raw_output", None)
        wav = getattr(self, "_sys_wav", None)

        sys_ok = False
        if getattr(self, "_sys_capture", None):
            try:
                sys_ok = self._sys_capture.stop()
            except Exception:
                sys_ok = False
        self._sys_capture = None

        try:
            if sys_ok and raw and os.path.isfile(raw):
                # Combina vídeo (com/sem mic) + som do sistema
                try:
                    self._mux(raw, wav, final, self._raw_has_audio)
                except Exception:
                    # Se o mux falhar, salva ao menos o vídeo bruto
                    try:
                        os.replace(raw, final)
                    except Exception:
                        pass
            else:
                # Sem som de sistema válido -> usa o vídeo bruto como final
                if raw and os.path.isfile(raw):
                    try:
                        os.replace(raw, final)
                    except Exception:
                        pass
        finally:
            for f in (raw, wav):
                try:
                    if f and os.path.isfile(f):
                        os.remove(f)
                except Exception:
                    pass

    def _mux(self, video_path, wav_path, output, video_has_audio):
        """Combina o vídeo com o áudio do sistema (e o mic, se houver) via FFmpeg."""
        ffmpeg = self.get_ffmpeg()
        fmt = self.config.get("format", "mp4")

        cmd = [ffmpeg, "-y", "-i", video_path, "-i", wav_path]

        if video_has_audio:
            # amix do áudio do vídeo (microfone) com o som do sistema
            cmd.extend([
                "-filter_complex",
                "[0:a][1:a]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]",
            ])
        else:
            # vídeo sem áudio -> usa só o som do sistema
            cmd.extend(["-map", "0:v", "-map", "1:a"])

        cmd.extend(["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"])
        if fmt in ("mp4", "mov"):
            cmd.extend(["-movflags", "+faststart"])
        cmd.append(output)

        startupinfo = self._make_startupinfo()
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=120,
        )

    def toggle_pause(self):
        """Pausa/resume a gravação (via suspend/resume do processo)."""
        if not self.is_recording or not self.process:
            return

        import ctypes
        kernel32 = ctypes.windll.kernel32

        if not self.is_paused:
            kernel32.DebugActiveProcess(self.process.pid)
            self.is_paused = True
            self.pause_time = time.time()
        else:
            kernel32.DebugActiveProcessStop(self.process.pid)
            self.is_paused = False
            if self.pause_time:
                self.total_paused += time.time() - self.pause_time
                self.pause_time = None

    def get_elapsed(self):
        if not self.start_time:
            return 0
        elapsed = time.time() - self.start_time - self.total_paused
        if self.is_paused and self.pause_time:
            elapsed -= (time.time() - self.pause_time)
        return max(0, elapsed)

    def get_elapsed_str(self):
        elapsed = int(self.get_elapsed())
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    # ------------------------------------------------------------------
    # Enumeração de dispositivos
    # ------------------------------------------------------------------
    _audio_cache = None
    _audio_cache_time = 0.0

    @staticmethod
    def list_audio_devices(force=False):
        """Lista dispositivos de áudio (microfones/entradas) via FFmpeg dshow.

        Usa um cache de 30s para evitar rodar o FFmpeg repetidamente (o que
        deixaria o início da gravação lento). force=True ignora o cache.
        """
        now = time.time()
        if (not force and Recorder._audio_cache is not None
                and (now - Recorder._audio_cache_time) < 30):
            return list(Recorder._audio_cache)

        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            return []

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

            result = subprocess.run(
                [ffmpeg, "-hide_banner", "-list_devices", "true",
                 "-f", "dshow", "-i", "dummy"],
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=15,
            )
            output = result.stderr or ""
            devices = []

            import re
            in_audio_section = False
            for line in output.split("\n"):
                low = line.lower()
                # Marcadores de seção do FFmpeg mais antigo
                if "directshow audio devices" in low:
                    in_audio_section = True
                    continue
                if "directshow video devices" in low:
                    in_audio_section = False
                    continue

                is_audio_line = ("(audio)" in low) or in_audio_section
                if not is_audio_line:
                    continue

                match = re.search(r'"([^"]+)"', line)
                if match:
                    name = match.group(1)
                    if not name.startswith("@device") and name not in devices:
                        devices.append(name)

            Recorder._audio_cache = list(devices)
            Recorder._audio_cache_time = now
            return devices
        except Exception:
            return list(Recorder._audio_cache) if Recorder._audio_cache else []

    @staticmethod
    def list_monitors():
        """Lista monitores disponíveis."""
        try:
            from screeninfo import get_monitors
            monitors = get_monitors()
            result = []
            for i, m in enumerate(monitors):
                result.append({
                    "index": i,
                    "name": f"Monitor {i + 1}",
                    "width": m.width,
                    "height": m.height,
                    "x": m.x,
                    "y": m.y,
                    "is_primary": m.is_primary if hasattr(m, 'is_primary') else (m.x == 0 and m.y == 0),
                })
            return result
        except ImportError:
            import ctypes
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            return [{
                "index": 0,
                "name": "Monitor 1",
                "width": w,
                "height": h,
                "x": 0,
                "y": 0,
                "is_primary": True,
            }]
