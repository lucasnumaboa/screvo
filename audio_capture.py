"""
Captura do áudio do SISTEMA (WASAPI loopback) — nativo do Windows, sem driver
virtual. Usa PyAudioWPatch. Se a biblioteca não estiver instalada, a captura
simplesmente fica indisponível (o app continua gravando vídeo + microfone).
"""

import os
import wave
import threading

try:
    import pyaudiowpatch as pyaudio
    _AVAILABLE = True
    _IMPORT_ERROR = None
except Exception as e:  # noqa
    pyaudio = None
    _AVAILABLE = False
    _IMPORT_ERROR = str(e)


class SystemAudioCapture:
    """Grava o som que sai pelos alto-falantes (loopback) num arquivo WAV."""

    def __init__(self):
        self._thread = None
        self._stop = threading.Event()
        self._wav_path = None
        self._error = None
        self._captured = False

    @staticmethod
    def available():
        return _AVAILABLE

    @staticmethod
    def import_error():
        return _IMPORT_ERROR

    @property
    def error(self):
        return self._error

    def start(self, wav_path):
        """Inicia a captura em thread separada. Retorna True se iniciou."""
        if not _AVAILABLE:
            self._error = f"PyAudioWPatch indisponível: {_IMPORT_ERROR}"
            return False
        self._wav_path = wav_path
        self._stop.clear()
        self._captured = False
        self._error = None
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        return True

    def _find_loopback(self, p):
        """Localiza o dispositivo de loopback WASAPI da saída padrão."""
        # Método direto (versões recentes do PyAudioWPatch)
        try:
            return p.get_default_wasapi_loopback()
        except Exception:
            pass
        # Busca manual por dispositivos marcados como loopback
        try:
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info.get("isLoopbackDevice", False):
                    return info
        except Exception:
            pass
        return None

    def _worker(self):
        p = stream = wf = None
        try:
            p = pyaudio.PyAudio()
            loopback = self._find_loopback(p)
            if not loopback:
                self._error = "Nenhum dispositivo de loopback WASAPI encontrado."
                return

            channels = int(loopback.get("maxInputChannels") or 2) or 2
            rate = int(loopback.get("defaultSampleRate") or 48000) or 48000
            chunk = 1024

            wf = wave.open(self._wav_path, "wb")
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # paInt16
            wf.setframerate(rate)

            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                frames_per_buffer=chunk,
                input=True,
                input_device_index=int(loopback["index"]),
            )

            while not self._stop.is_set():
                data = stream.read(chunk, exception_on_overflow=False)
                wf.writeframes(data)
                self._captured = True
        except Exception as e:
            self._error = str(e)
        finally:
            try:
                if stream:
                    stream.stop_stream()
                    stream.close()
            except Exception:
                pass
            try:
                if wf:
                    wf.close()
            except Exception:
                pass
            try:
                if p:
                    p.terminate()
            except Exception:
                pass

    def stop(self):
        """Para a captura. Retorna True se um WAV com conteúdo foi gerado."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=6)
        try:
            return bool(
                self._captured
                and self._wav_path
                and os.path.isfile(self._wav_path)
                and os.path.getsize(self._wav_path) > 1000
            )
        except Exception:
            return False
