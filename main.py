"""
Screvo — Entry Point
Gravador de tela com atalho global, overlay flutuante, transcrição offline e
resumo por IA.
"""

import sys
import os

# Garante que o diretório do script está no PATH (para imports)
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))

os.chdir(app_dir)
sys.path.insert(0, app_dir)

# Adiciona ffmpeg ao PATH
ffmpeg_bin = os.path.join(app_dir, "ffmpeg", "bin")
if os.path.isdir(ffmpeg_bin):
    os.environ["PATH"] = ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")


def _install_excepthook():
    """Impede que exceções não tratadas fechem o app (PyQt6 aborta por padrão).

    Registra o erro num log e mostra um aviso, mas mantém o app aberto.
    """
    import traceback

    log_path = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "VideoRecorder", "error.log"
    )

    def handle(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                from datetime import datetime
                f.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
                f.write(msg)
        except Exception:
            pass
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                None, "Ocorreu um erro",
                "Um erro inesperado aconteceu, mas o aplicativo continua aberto.\n\n"
                f"Detalhes:\n{exc_value}\n\nLog: {log_path}"
            )
        except Exception:
            pass

    sys.excepthook = handle


def _ensure_audio_deps():
    """Garante a biblioteca de captura do som do sistema (WASAPI loopback).

    Se estiver faltando E o app estiver rodando a partir do código-fonte
    (não empacotado), tenta instalar automaticamente via pip — assim o
    usuário não precisa fazer nada. Falhas são ignoradas (o app segue
    gravando vídeo + microfone).
    """
    try:
        import pyaudiowpatch  # noqa
        return
    except Exception:
        pass

    if getattr(sys, "frozen", False):
        return  # empacotado: nada a instalar em runtime

    try:
        import subprocess
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "PyAudioWPatch"],
            timeout=240,
            creationflags=creationflags,
        )
    except Exception:
        pass


def main():
    _install_excepthook()
    _ensure_audio_deps()
    from app import ScrevoApp
    app = ScrevoApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
