import json
import os
import sys

DEFAULT_CONFIG = {
    "hotkey": "ctrl+shift+r",
    "output_folder": os.path.join(os.path.expanduser("~"), "Videos", "VideoRecorder"),
    "format": "mp4",
    "fps": 30,
    "quality": "high",
    "codec": "h264",
    "audio_enabled": True,
    "audio_mode": "system_mic",
    "audio_device": "auto",
    "volume": 100,
    "mute_during_recording": False,
    "start_hidden": False,
    "start_with_windows": False,
    "overlay_position": "bottom",
    "show_tray_icon": True,
    "parakeet_url": (
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
        "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2"
    ),
    # Provedor de IA para resumo de legendas
    "ia_provider": "",         # gemini | claude | openai | deepseek
    "ia_model": "",            # nome do modelo (ex: gpt-4o-mini, gemini-1.5-flash)
    "ia_api_key": "",
    "ia_template": "geral",    # template de resumo (ver summary_templates.py)
    "ia_models": {},           # modelo lembrado por provedor {provedor: modelo}
}


def get_app_dir():
    """Retorna o diretório do aplicativo (onde o exe está ou pasta do script)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_config_path():
    """Retorna caminho do arquivo de configuração."""
    app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    config_dir = os.path.join(app_data, "VideoRecorder")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.json")


def get_ffmpeg_path():
    """Retorna caminho do FFmpeg bundled ou no PATH."""
    app_dir = get_app_dir()
    # Tenta achar na pasta ffmpeg/bin relativa ao app
    bundled = os.path.join(app_dir, "ffmpeg", "bin", "ffmpeg.exe")
    if os.path.isfile(bundled):
        return bundled
    # Tenta no PATH
    import shutil
    path_ffmpeg = shutil.which("ffmpeg")
    if path_ffmpeg:
        return path_ffmpeg
    return None


class Config:
    def __init__(self):
        self._path = get_config_path()
        self._data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        try:
            if os.path.isfile(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data.update(saved)
        except (json.JSONDecodeError, IOError):
            pass

    def save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    def get(self, key, default=None):
        return self._data.get(key, default if default is not None else DEFAULT_CONFIG.get(key))

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def get_all(self):
        return dict(self._data)

    def reset(self):
        self._data = dict(DEFAULT_CONFIG)
        self.save()
