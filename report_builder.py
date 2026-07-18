"""
Extração de áudio, extração de frames e geração de RELATÓRIO COMPLETO.

O relatório encadeia: transcrição -> OCR da tela -> IA. A IA recebe a
transcrição e o texto da tela (ambos com tempos) e escreve um relatório em
Markdown, podendo inserir marcadores [[FRAME:mm:ss]] que são substituídos por
capturas reais extraídas do vídeo e embutidas no corpo do relatório.
"""

import os
import re
import json
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal
from config import get_ffmpeg_path

FRAME_RE = re.compile(
    r"\[\[FRAME:\s*([0-9:.]+)\s*(?:\|\s*crop\s*=\s*([0-9, ]+))?\s*\]\]",
    re.IGNORECASE,
)


def _flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def parse_time(s):
    """Converte '83', '83.5', '1:23' ou '1:02:03' em segundos (float)."""
    s = s.strip()
    if ":" in s:
        parts = [float(p) for p in s.split(":")]
        secs = 0.0
        for p in parts:
            secs = secs * 60 + p
        return secs
    return float(s)


def _mmss(seconds):
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


# --------------------------- Áudio ---------------------------
def extract_audio(video_path, fmt="mp3"):
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg não encontrado.")
    out = os.path.splitext(video_path)[0] + "." + fmt
    if fmt == "mp3":
        codec = ["-acodec", "libmp3lame", "-q:a", "2"]
    elif fmt in ("m4a", "aac"):
        codec = ["-c:a", "aac", "-b:a", "192k"]
    else:
        codec = []
    cmd = [ffmpeg, "-y", "-i", video_path, "-vn", *codec, out]
    subprocess.run(cmd, capture_output=True, creationflags=_flags(), timeout=600)
    if not os.path.isfile(out) or os.path.getsize(out) < 500:
        raise RuntimeError("Falha ao extrair o áudio (codec indisponível?).")
    return out


class AudioExtractWorker(QThread):
    finished_ok = pyqtSignal(str, str)   # (out_path, video_path)
    failed = pyqtSignal(str, str)

    def __init__(self, video_path, fmt="mp3", parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.fmt = fmt

    def run(self):
        try:
            out = extract_audio(self.video_path, self.fmt)
            self.finished_ok.emit(out, self.video_path)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e), self.video_path)


# --------------------------- Frames ---------------------------
def extract_frame(video_path, seconds, out_path, crop=None):
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg não encontrado.")
    cmd = [ffmpeg, "-y", "-ss", str(max(0.0, seconds)), "-i", video_path,
           "-frames:v", "1"]
    if crop:
        try:
            x, y, w, h = crop
            cmd += ["-vf", f"crop={w}:{h}:{x}:{y}"]
        except Exception:
            pass
    cmd += ["-q:v", "2", "-update", "1", out_path]
    subprocess.run(cmd, capture_output=True, creationflags=_flags(), timeout=120)
    return os.path.isfile(out_path)


# --------------------------- Relatório ---------------------------
def _build_context(segments, ocr_text):
    lines = []
    duration = 0.0
    if segments:
        duration = max((s.get("end", 0) for s in segments), default=0.0)
    lines.append(f"Duração aproximada do vídeo: {_mmss(duration)} ({int(duration)} s).\n")

    lines.append("=== TRANSCRIÇÃO (com tempos) ===")
    if segments:
        for s in segments:
            spk = f"{s['speaker']}: " if s.get("speaker") else ""
            lines.append(f"[{_mmss(s.get('start', 0))}] {spk}{s.get('text', '')}")
    else:
        lines.append("(sem transcrição)")

    lines.append("\n=== TEXTO DA TELA (OCR, com tempos) ===")
    lines.append(ocr_text.strip() or "(sem texto de tela)")
    return "\n".join(lines)


def build_report(video_path, segments, ocr_text, provider, model, api_key,
                 status_cb=None):
    import ai_summarizer

    base_dir = os.path.dirname(video_path)
    base = os.path.splitext(os.path.basename(video_path))[0]

    if status_cb:
        status_cb("Gerando relatório com a IA...")
    context = _build_context(segments, ocr_text)
    md = ai_summarizer.generate_report(provider, model, api_key, context)

    # Substitui marcadores [[FRAME:...]] por capturas reais
    imgs_dirname = base + "_relatorio_arquivos"
    imgs_dir = os.path.join(base_dir, imgs_dirname)
    counter = {"i": 0}

    def _repl(m):
        t = parse_time(m.group(1))
        crop = None
        if m.group(2):
            nums = [int(n) for n in re.findall(r"\d+", m.group(2))]
            if len(nums) == 4:
                crop = nums
        counter["i"] += 1
        idx = counter["i"]
        fname = f"frame_{idx:02d}.png"
        os.makedirs(imgs_dir, exist_ok=True)
        out = os.path.join(imgs_dir, fname)
        if status_cb:
            status_cb(f"Capturando frame em {_mmss(t)}...")
        try:
            if extract_frame(video_path, t, out, crop):
                return (f"\n\n![Momento {_mmss(t)}]({imgs_dirname}/{fname})\n\n")
        except Exception:
            pass
        return ""  # falhou -> remove o marcador

    md = FRAME_RE.sub(_repl, md)

    # Fallback: se a IA não inseriu NENHUMA captura (comum em modelos locais
    # pequenos), inserimos uma imagem em cada BLOCO DE TEMPO citado no texto —
    # inline, logo após a linha — espalhando conforme os blocos do relatório.
    if counter["i"] == 0:
        if status_cb:
            status_cb("Adicionando capturas automaticamente...")
        duration = 0.0
        if segments:
            duration = max((s.get("end", 0) for s in segments), default=0.0)
        for mm in re.finditer(r"(\d{1,2}):(\d{2})", ocr_text or ""):
            duration = max(duration, int(mm.group(1)) * 60 + int(mm.group(2)))

        md = _insert_frames_by_text(md, video_path, imgs_dir, imgs_dirname,
                                    duration, counter, status_cb)

        # Se o texto não tinha nenhum tempo, distribui capturas pela duração.
        if counter["i"] == 0:
            times = _uniform_times(duration)
            if times:
                os.makedirs(imgs_dir, exist_ok=True)
                gallery = ["\n\n## 📸 Capturas do vídeo\n"]
                for t in times:
                    counter["i"] += 1
                    fname = f"frame_{counter['i']:02d}.png"
                    out = os.path.join(imgs_dir, fname)
                    try:
                        if extract_frame(video_path, t, out):
                            gallery.append(
                                f"**{_mmss(t)}**\n\n"
                                f"![Momento {_mmss(t)}]({imgs_dirname}/{fname})\n"
                            )
                    except Exception:
                        pass
                if len(gallery) > 1:
                    md = md.rstrip() + "\n" + "\n".join(gallery) + "\n"

    report_path = os.path.join(base_dir, base + "_relatorio.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    return report_path


def _insert_frames_by_text(md, video_path, imgs_dir, imgs_dirname, duration,
                           counter, status_cb, max_n=8):
    """Insere uma captura logo após cada linha que cita um tempo (mm:ss).

    Usa o 1º tempo da linha (início do bloco). Evita duplicar tempos próximos
    e respeita a duração do vídeo.
    """
    ts_re = re.compile(r"(\d{1,2}):(\d{2})")
    out = []
    used = []

    def _ok(t):
        if duration and t > duration + 2:
            return False
        return all(abs(u - t) >= 3 for u in used)

    for line in md.splitlines():
        out.append(line)
        if counter["i"] >= max_n:
            continue
        m = ts_re.search(line)
        if not m:
            continue
        t = int(m.group(1)) * 60 + int(m.group(2))
        if not _ok(t):
            continue
        counter["i"] += 1
        fname = f"frame_{counter['i']:02d}.png"
        os.makedirs(imgs_dir, exist_ok=True)
        outp = os.path.join(imgs_dir, fname)
        if status_cb:
            status_cb(f"Capturando frame em {_mmss(t)}...")
        try:
            if extract_frame(video_path, t, outp):
                out.append(f"\n![Momento {_mmss(t)}]({imgs_dirname}/{fname})\n")
                used.append(t)
            else:
                counter["i"] -= 1
        except Exception:
            counter["i"] -= 1
    return "\n".join(out)


def _uniform_times(duration, n=5):
    """Tempos distribuídos uniformemente pela duração (fallback)."""
    if not duration or duration <= 2:
        return []
    n = min(n, 5)
    step = duration / (n + 1)
    return [round(step * (i + 1), 1) for i in range(n)]


class ReportWorker(QThread):
    """Encadeia transcrição -> OCR -> relatório IA (com capturas)."""
    status = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(str, str)   # (report_path, video_path)
    failed = pyqtSignal(str, str)

    def __init__(self, video_path, provider, model, api_key, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.provider = provider
        self.model = model
        self.api_key = api_key

    def run(self):
        try:
            base = os.path.splitext(self.video_path)[0]
            txt_path = base + ".txt"
            seg_path = base + ".segments.json"
            tela_path = base + "_tela.txt"

            # 1) Transcrição (não fatal — se falhar, segue só com o OCR)
            if not (os.path.isfile(txt_path) and os.path.isfile(seg_path)):
                self.status.emit("Etapa 1/3 — Transcrevendo áudio...")
                try:
                    from local_transcriber import LocalTranscriber
                    lt = LocalTranscriber(config=None)
                    lt.status.connect(self.status)
                    lt.progress.connect(self.progress)
                    lt.transcribe_sync(self.video_path)
                except Exception:
                    self.status.emit("Transcrição indisponível (seguindo sem áudio)...")

            segments = []
            if os.path.isfile(seg_path):
                try:
                    with open(seg_path, "r", encoding="utf-8") as f:
                        segments = json.load(f)
                except Exception:
                    segments = []

            # 2) OCR da tela (não fatal)
            if not os.path.isfile(tela_path):
                self.status.emit("Etapa 2/3 — Lendo texto da tela (OCR)...")
                try:
                    import ocr_screen
                    ocr_screen.run_ocr(
                        self.video_path,
                        status_cb=self.status.emit,
                        progress_cb=self.progress.emit,
                    )
                except Exception:
                    self.status.emit("OCR indisponível (seguindo sem texto da tela)...")
            ocr_text = ""
            if os.path.isfile(tela_path):
                try:
                    with open(tela_path, "r", encoding="utf-8") as f:
                        ocr_text = f.read()
                except Exception:
                    ocr_text = ""

            # Precisa de pelo menos uma fonte de conteúdo
            if not segments and not ocr_text.strip():
                raise RuntimeError(
                    "Não foi possível obter transcrição nem texto de tela do "
                    "vídeo, então não há conteúdo para o relatório."
                )

            # 3) Relatório
            self.status.emit("Etapa 3/3 — Montando relatório...")
            report_path = build_report(
                self.video_path, segments, ocr_text,
                self.provider, self.model, self.api_key,
                status_cb=self.status.emit,
            )
            self.finished_ok.emit(report_path, self.video_path)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e), self.video_path)
