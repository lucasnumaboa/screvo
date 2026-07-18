"""
OCR da tela — extrai o texto que APARECE no vídeo (slides, código, erros...).

100% local. Extrai frames com o FFmpeg (1 a cada N segundos), roda OCR em cada
um e deduplica telas repetidas. O resultado vai para <video>_tela.txt.

Motores suportados (nesta ordem):
  1. winocr  — OCR nativo do Windows (offline, sem binário externo).
  2. pytesseract — precisa do Tesseract instalado (tesseract.exe no PATH).
"""

import os
import sys
import subprocess
import tempfile
import difflib

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from config import get_ffmpeg_path


def _no_window_flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _try_import(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


def detect_engine(allow_install=True):
    """Retorna 'winocr', 'tesseract' ou None."""
    if _try_import("winocr"):
        return "winocr"
    if _try_import("pytesseract"):
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return "tesseract"
        except Exception:
            pass
    # Tenta instalar winocr (só rodando a partir do código-fonte)
    if allow_install and not getattr(sys, "frozen", False):
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", "winocr"],
                timeout=600, creationflags=_no_window_flags(),
            )
            if _try_import("winocr"):
                return "winocr"
        except Exception:
            pass
    return None


def _ocr_image(path, engine):
    from PIL import Image
    img = Image.open(path).convert("RGB")
    if engine == "winocr":
        import winocr
        res = None
        for lang in ("pt-BR", "pt", None):
            try:
                res = (winocr.recognize_pil_sync(img, lang) if lang
                       else winocr.recognize_pil_sync(img))
                break
            except Exception:
                continue
        if res is None:
            return ""
        if isinstance(res, dict):
            return (res.get("text") or "").strip()
        return (getattr(res, "text", "") or "").strip()
    elif engine == "tesseract":
        import pytesseract
        for lang in ("por", "por+eng", None):
            try:
                return pytesseract.image_to_string(
                    img, lang=lang) if lang else pytesseract.image_to_string(img)
            except Exception:
                continue
        return ""
    return ""


def run_ocr(video_path, interval=3, status_cb=None, progress_cb=None):
    """Executa o OCR de forma síncrona. Escreve <video>_tela.txt e o retorna.

    Lança exceção em caso de erro. status_cb(str) e progress_cb(cur, total)
    são chamados para feedback (opcionais).
    """
    def _status(m):
        if status_cb:
            status_cb(m)

    def _progress(c, t):
        if progress_cb:
            progress_cb(c, t)

    temp_dir = tempfile.mkdtemp(prefix="screvo_ocr_")
    try:
        engine = detect_engine()
        if not engine:
            raise RuntimeError(
                "Nenhum motor de OCR disponível. Instale o Tesseract "
                "(https://github.com/UB-Mannheim/tesseract/wiki) ou o pacote "
                "Python 'winocr' (pip install winocr)."
            )

        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            raise RuntimeError("FFmpeg não encontrado.")

        _status("Extraindo frames do vídeo...")
        pattern = os.path.join(temp_dir, "f_%05d.png")
        # Resolução NATIVA — reduzir destrói a legibilidade para o OCR.
        cmd = [ffmpeg, "-y", "-i", video_path, "-vf", f"fps=1/{interval}", pattern]
        subprocess.run(cmd, capture_output=True,
                       creationflags=_no_window_flags(), timeout=1800)

        frames = sorted(f for f in os.listdir(temp_dir) if f.endswith(".png"))
        if not frames:
            raise RuntimeError("Não foi possível extrair frames do vídeo.")

        _status(f"Lendo texto da tela ({engine})...")
        blocks = []
        prev_text = ""
        total = len(frames)
        for i, fname in enumerate(frames):
            text = _clean(_ocr_image(os.path.join(temp_dir, fname), engine))
            if text and difflib.SequenceMatcher(None, prev_text, text).ratio() < 0.9:
                secs = i * interval
                ts = f"{secs // 60:02d}:{secs % 60:02d}"
                blocks.append(f"[{ts}]\n{text}")
                prev_text = text
            _progress(i + 1, total)

        if not blocks:
            raise RuntimeError("Nenhum texto foi detectado na tela.")

        out_path = os.path.splitext(video_path)[0] + "_tela.txt"
        header = f"Texto capturado da tela (OCR via {engine})\n" + "=" * 34 + "\n\n"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(header + "\n\n".join(blocks))
        return out_path
    finally:
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


class OcrWorker(QThread):
    progress = pyqtSignal(int, int)   # atual, total
    status = pyqtSignal(str)
    finished_ok = pyqtSignal(str, str)  # (txt_path, video_path)
    failed = pyqtSignal(str, str)       # (erro, video_path)

    def __init__(self, video_path, interval=3, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.interval = interval

    def run(self):
        try:
            out_path = run_ocr(
                self.video_path, self.interval,
                status_cb=self.status.emit,
                progress_cb=self.progress.emit,
            )
            self.finished_ok.emit(out_path, self.video_path)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e), self.video_path)


import re as _re


def _clean(text):
    """Remove linhas de ruído (poucas letras / muito símbolo)."""
    out = []
    for ln in text.splitlines():
        ln = ln.rstrip()
        s = ln.strip()
        if len(s) < 3:
            continue
        alnum = sum(c.isalnum() for c in s)
        if alnum / max(1, len(s)) < 0.55:
            continue  # linha dominada por símbolos = ruído
        if not _re.search(r"[A-Za-zÀ-ÿ]{3,}", s):
            continue  # sem nenhuma palavra de verdade
        out.append(ln)
    return "\n".join(out).strip()
