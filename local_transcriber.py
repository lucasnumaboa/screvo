"""
Transcrição de áudio LOCAL (offline) com NVIDIA Parakeet TDT 0.6b v3
via sherpa-onnx (ONNX int8 — leve e rápido, sem PyTorch/NeMo).
Suporta 25 idiomas, incluindo português.

O modelo (~600 MB) é baixado sob demanda na 1ª vez e fica em cache; depois
roda totalmente na máquina, sem enviar áudio para nenhum servidor. As
bibliotecas (sherpa-onnx / numpy) são instaladas automaticamente no primeiro
uso quando rodando a partir do código-fonte.
"""

import os
import sys
import subprocess
import tempfile
import tarfile
import threading

from PyQt6.QtCore import QObject, pyqtSignal
from config import get_ffmpeg_path


PARAKEET_DIRNAME = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
PARAKEET_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2"
)


def _models_dir():
    d = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "VideoRecorder", "models"
    )
    os.makedirs(d, exist_ok=True)
    return d


def _no_window_kwargs():
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = subprocess.CREATE_NO_WINDOW
    return startupinfo, creationflags


class LocalTranscriber(QObject):
    """Transcreve o áudio de um vídeo localmente com Parakeet V3."""
    progress = pyqtSignal(int, int)   # atual, total
    finished = pyqtSignal(str)        # caminho do .txt gerado
    error = pyqtSignal(str)           # mensagem de erro
    status = pyqtSignal(str)          # status textual

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config

    @staticmethod
    def available():
        """Disponível se as libs estão presentes (empacotadas) OU se dá para
        instalá-las sob demanda (rodando a partir do código-fonte)."""
        import importlib.util
        if importlib.util.find_spec("sherpa_onnx") is not None:
            return True
        return not getattr(sys, "frozen", False)

    @staticmethod
    def model_downloaded():
        return os.path.isfile(
            os.path.join(_models_dir(), PARAKEET_DIRNAME, "encoder.int8.onnx")
        )

    def transcribe(self, video_path):
        thread = threading.Thread(
            target=self._worker, args=(video_path,), daemon=True
        )
        thread.start()

    # ------------------------------------------------------------------
    def _pip_install(self, *packages):
        if getattr(sys, "frozen", False):
            raise RuntimeError("Componente não incluído nesta versão empacotada.")
        _, creationflags = _no_window_kwargs()
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", *packages],
            timeout=1200,
            creationflags=creationflags,
        )

    def _ensure_sherpa(self):
        try:
            import sherpa_onnx  # noqa
            import numpy  # noqa
            return
        except Exception:
            pass
        self.status.emit("Instalando motor Parakeet (uma vez, pode demorar)...")
        self._pip_install("sherpa-onnx", "numpy")
        import sherpa_onnx  # noqa
        import numpy  # noqa

    def _extract_audio(self, video_path, wav_path):
        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            raise RuntimeError("FFmpeg não encontrado.")
        cmd = [
            ffmpeg, "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            wav_path,
        ]
        startupinfo, creationflags = _no_window_kwargs()
        subprocess.run(
            cmd, capture_output=True, startupinfo=startupinfo,
            creationflags=creationflags, timeout=600,
        )

    def _ensure_parakeet_model(self):
        """Baixa e extrai o modelo Parakeet (se ainda não estiver em cache)."""
        models = _models_dir()
        model_dir = os.path.join(models, PARAKEET_DIRNAME)
        encoder = os.path.join(model_dir, "encoder.int8.onnx")
        if os.path.isfile(encoder):
            return model_dir  # já baixado

        import requests
        url = PARAKEET_URL
        if self.config is not None:
            url = self.config.get("parakeet_url", PARAKEET_URL) or PARAKEET_URL

        tar_path = os.path.join(models, PARAKEET_DIRNAME + ".tar.bz2")
        self.status.emit("Baixando modelo Parakeet V3 (uma vez)...")

        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0) or 0)
            done = 0
            with open(tar_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=262144):
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = int(done / total * 100)
                        self.progress.emit(pct, 100)
                        self.status.emit(f"Baixando modelo Parakeet V3... {pct}%")

        self.status.emit("Extraindo modelo Parakeet...")
        with tarfile.open(tar_path, "r:bz2") as tar:
            tar.extractall(models)
        try:
            os.remove(tar_path)
        except Exception:
            pass

        if not os.path.isfile(encoder):
            raise RuntimeError("Falha ao extrair o modelo Parakeet.")
        return model_dir

    def download_model(self):
        """Baixa o modelo em segundo plano (para o botão 'Baixar modelo')."""
        def _dl():
            try:
                self._ensure_sherpa()
                self._ensure_parakeet_model()
                self.progress.emit(100, 100)
                self.status.emit("Modelo Parakeet pronto!")
                self.finished.emit("")  # "" = concluiu download, sem legenda
            except Exception as e:
                self.error.emit(f"Erro ao baixar o modelo: {str(e)}")
        threading.Thread(target=_dl, daemon=True).start()

    def _transcribe_parakeet(self, wav_path):
        """Transcreve o WAV (16k mono) usando Parakeet via sherpa-onnx."""
        self._ensure_sherpa()
        import sherpa_onnx
        import numpy as np
        import wave

        model_dir = self._ensure_parakeet_model()

        self.status.emit("Carregando modelo Parakeet...")
        recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=os.path.join(model_dir, "encoder.int8.onnx"),
            decoder=os.path.join(model_dir, "decoder.int8.onnx"),
            joiner=os.path.join(model_dir, "joiner.int8.onnx"),
            tokens=os.path.join(model_dir, "tokens.txt"),
            num_threads=max(2, (os.cpu_count() or 4)),
            decoding_method="greedy_search",
            model_type="nemo_transducer",
        )

        with wave.open(wav_path) as wf:
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        # Decodifica em janelas de 30s (progresso + memória controlada)
        window = 30 * sr
        n = len(samples)
        total_chunks = max(1, (n + window - 1) // window)
        parts = []
        self.status.emit("Transcrevendo com Parakeet...")
        for idx in range(total_chunks):
            chunk = samples[idx * window:(idx + 1) * window]
            if len(chunk) == 0:
                continue
            stream = recognizer.create_stream()
            stream.accept_waveform(sr, chunk)
            recognizer.decode_stream(stream)
            txt = (stream.result.text or "").strip()
            if txt:
                parts.append(txt)
            self.progress.emit(idx + 1, total_chunks)

        return " ".join(parts).strip()

    def _worker(self, video_path):
        temp_dir = tempfile.mkdtemp(prefix="vr_local_")
        wav_path = os.path.join(temp_dir, "audio.wav")
        try:
            self.status.emit("Extraindo áudio...")
            self._extract_audio(video_path, wav_path)
            if not os.path.isfile(wav_path) or os.path.getsize(wav_path) < 1000:
                self.error.emit("Não foi possível extrair áudio do vídeo.")
                return

            full_text = self._transcribe_parakeet(wav_path)

            if not full_text:
                self.error.emit(
                    "Nenhum texto foi transcrito. O áudio pode estar em silêncio."
                )
                return

            txt_path = os.path.splitext(video_path)[0] + ".txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(full_text)

            self.progress.emit(100, 100)
            self.status.emit("Transcrição concluída!")
            self.finished.emit(txt_path)

        except Exception as e:
            self.error.emit(f"Erro na transcrição local: {str(e)}")
        finally:
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
