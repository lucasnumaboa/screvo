"""
Transcrição de áudio via API Whisper — chunked em 1 minuto.
POST <whisper_url>  (padrão: https://whisper.manerostream.com.br/transcribe)
Basic Auth: usuário/senha vindos das Configurações (padrão: admin/admin123)
Form-data: audio (binary), model=turbo, language=Portuguese, task=transcribe
"""

import os
import subprocess
import tempfile
import threading
import requests
from config import get_ffmpeg_path

from PyQt6.QtCore import QObject, pyqtSignal


class Transcriber(QObject):
    """Transcreve áudio de vídeo via API Whisper, enviando chunks de 1 minuto."""
    progress = pyqtSignal(int, int)   # chunk_atual, total_chunks
    finished = pyqtSignal(str)        # caminho do arquivo .txt gerado
    error = pyqtSignal(str)           # mensagem de erro
    status = pyqtSignal(str)          # status textual

    DEFAULT_URL = "https://whisper.manerostream.com.br/transcribe"
    DEFAULT_USER = "admin"
    DEFAULT_PASSWORD = "admin123"
    CHUNK_DURATION = 60  # 1 minuto em segundos

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self._refresh_creds()

    def _refresh_creds(self):
        """Lê endpoint/credenciais da config (chamado a cada transcrição)."""
        config = self.config
        if config is not None:
            self.api_url = config.get("whisper_url", self.DEFAULT_URL) or self.DEFAULT_URL
            user = config.get("whisper_user", self.DEFAULT_USER) or self.DEFAULT_USER
            pwd = config.get("whisper_password", self.DEFAULT_PASSWORD)
            if pwd is None:
                pwd = self.DEFAULT_PASSWORD
        else:
            self.api_url = self.DEFAULT_URL
            user = self.DEFAULT_USER
            pwd = self.DEFAULT_PASSWORD
        self.auth = (user, pwd)

    def transcribe(self, video_path):
        """Inicia transcrição em thread separada."""
        self._refresh_creds()  # relê credenciais atualizadas nas configurações
        thread = threading.Thread(
            target=self._transcribe_worker,
            args=(video_path,),
            daemon=True
        )
        thread.start()

    def _transcribe_worker(self, video_path):
        """Worker que executa a transcrição."""
        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            self.error.emit("FFmpeg não encontrado.")
            return

        temp_dir = tempfile.mkdtemp(prefix="vr_transcribe_")

        try:
            # 1. Obtém duração do vídeo
            self.status.emit("Analisando vídeo...")
            duration = self._get_duration(ffmpeg, video_path)
            if duration <= 0:
                self.error.emit("Não foi possível determinar a duração do vídeo.")
                return

            # 2. Calcula chunks
            num_chunks = max(1, int(duration // self.CHUNK_DURATION) + (1 if duration % self.CHUNK_DURATION > 0 else 0))
            self.status.emit(f"Dividindo áudio em {num_chunks} parte(s)...")

            # 3. Extrai e divide áudio em chunks
            chunks = []
            for i in range(num_chunks):
                start = i * self.CHUNK_DURATION
                chunk_path = os.path.join(temp_dir, f"chunk_{i:04d}.wav")

                cmd = [
                    ffmpeg, "-y",
                    "-i", video_path,
                    "-ss", str(start),
                    "-t", str(self.CHUNK_DURATION),
                    "-vn",  # Sem vídeo
                    "-acodec", "pcm_s16le",
                    "-ar", "16000",
                    "-ac", "1",
                    chunk_path
                ]

                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    startupinfo=startupinfo,
                    timeout=120
                )

                if os.path.isfile(chunk_path) and os.path.getsize(chunk_path) > 1000:
                    chunks.append(chunk_path)

            if not chunks:
                self.error.emit("Não foi possível extrair áudio do vídeo.")
                return

            # 4. Envia cada chunk para a API
            all_text = []
            total = len(chunks)
            last_error = None

            for i, chunk_path in enumerate(chunks):
                self.status.emit(f"Transcrevendo parte {i + 1} de {total}...")
                self.progress.emit(i + 1, total)

                try:
                    text = self._send_to_api(chunk_path)
                    if text and text.strip():
                        all_text.append(text.strip())
                except Exception as e:
                    last_error = str(e)
                    self.status.emit(f"Erro na parte {i + 1}: {str(e)[:60]}")
                    # Continua com próximos chunks

            # 5. Junta tudo e salva
            if not all_text:
                if last_error:
                    self.error.emit(
                        f"Nenhum texto foi transcrito.\n\nCausa provável: {last_error}"
                    )
                else:
                    self.error.emit(
                        "Nenhum texto foi transcrito. O áudio pode estar em silêncio "
                        "(verifique se o microfone/som do sistema foi capturado)."
                    )
                return

            full_text = "\n".join(all_text)

            # Salva com mesmo nome do vídeo + .txt
            video_name = os.path.splitext(video_path)[0]
            txt_path = video_name + ".txt"

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(full_text)

            self.status.emit("Transcrição concluída!")
            self.finished.emit(txt_path)

        except Exception as e:
            self.error.emit(f"Erro: {str(e)}")

        finally:
            # Limpa chunks temporários
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    def _get_duration(self, ffmpeg, video_path):
        """Obtém duração do vídeo em segundos via ffprobe."""
        ffprobe = ffmpeg.replace("ffmpeg.exe", "ffprobe.exe")
        if not os.path.isfile(ffprobe):
            ffprobe = ffmpeg  # fallback

        cmd = [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                timeout=30
            )
            return float(result.stdout.strip())
        except Exception:
            return 0

    def _send_to_api(self, audio_path):
        """Envia chunk de áudio para a API Whisper."""
        with open(audio_path, "rb") as f:
            files = {
                "audio": (os.path.basename(audio_path), f, "audio/wav")
            }
            data = {
                "model": "turbo",
                "language": "Portuguese",
                "task": "transcribe",
            }

            response = requests.post(
                self.api_url,
                files=files,
                data=data,
                auth=self.auth,
                timeout=120,
            )

            if response.status_code == 200:
                # Tenta pegar texto da resposta
                try:
                    json_resp = response.json()
                    # Pode ser {"text": "..."} ou similar
                    if isinstance(json_resp, dict):
                        return json_resp.get("text", json_resp.get("result", str(json_resp)))
                    return str(json_resp)
                except Exception:
                    return response.text
            elif response.status_code == 401:
                raise Exception(
                    "Falha de autenticação (usuário/senha incorretos). "
                    "Ajuste em Configurações → Speech."
                )
            else:
                raise Exception(f"API retornou status {response.status_code}: {response.text[:200]}")
