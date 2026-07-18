"""
IA local RODANDO DENTRO DO APP (sem programas externos).

Usa o llama.cpp via `llama-cpp-python`: o app baixa o modelo Gemma (arquivo
GGUF, do Hugging Face) e carrega em processo. Toda a pergunta/resposta acontece
dentro do Screvo. A inferência padrão é por CPU (funciona em qualquer máquina,
inclusive placas AMD); por isso a sugestão de modelo é baseada na RAM.

`llama-cpp-python` é instalado sob demanda na 1ª vez (rodando do código-fonte).
"""

import os
import sys
import subprocess
import requests

from PyQt6.QtCore import QThread, pyqtSignal


# Modelos Gemma em GGUF (re-uploads abertos, sem token). Ajuste as URLs se
# precisar de outra versão/quantização.
LLM_MODELS = [
    {
        "key": "gemma2-2b",
        "label": "Gemma 2 · 2B (leve)",
        "file": "gemma-2-2b-it-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf",
        "min_ram": 0,      # roda em qualquer máquina
        "size": "~1,7 GB",
        "note": "~1,7 GB — roda em quase tudo",
    },
    {
        "key": "gemma2-9b",
        "label": "Gemma 2 · 9B",
        "file": "gemma-2-9b-it-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/gemma-2-9b-it-GGUF/resolve/main/gemma-2-9b-it-Q4_K_M.gguf",
        "min_ram": 12,
        "size": "~5,8 GB",
        "note": "~5,8 GB — recomendado 12+ GB de RAM",
    },
    {
        "key": "gemma2-27b",
        "label": "Gemma 2 · 27B",
        "file": "gemma-2-27b-it-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/gemma-2-27b-it-GGUF/resolve/main/gemma-2-27b-it-Q4_K_M.gguf",
        "min_ram": 32,
        "size": "~16 GB",
        "note": "~16 GB — recomendado 32+ GB de RAM",
    },
]

_llm = None
_loaded_path = None


def _flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def models_dir():
    d = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "VideoRecorder", "models", "llm",
    )
    os.makedirs(d, exist_ok=True)
    return d


def model_by_key(key):
    for m in LLM_MODELS:
        if m["key"] == key:
            return m
    return None


def model_path(model):
    if isinstance(model, str):
        model = model_by_key(model)
    if not model:
        return None
    return os.path.join(models_dir(), model["file"])


def is_downloaded(key):
    p = model_path(key)
    return bool(p) and os.path.isfile(p) and os.path.getsize(p) > 1_000_000


def model_enabled(ram_gb, model):
    if model["min_ram"] <= 0:
        return True
    return bool(ram_gb) and ram_gb >= model["min_ram"]


def recommend(ram_gb):
    best = LLM_MODELS[0]["key"]
    for m in LLM_MODELS:
        if model_enabled(ram_gb, m):
            best = m["key"]
    return best


# Índice oficial com wheels PRÉ-COMPILADAS (CPU) — evita compilar do zero.
_LLAMA_CPU_INDEX = "https://abetlen.github.io/llama-cpp-python/whl/cpu"


def llama_installed():
    try:
        import llama_cpp  # noqa
        return True
    except Exception:
        return False


def ensure_llama(status_cb=None):
    if llama_installed():
        return
    if getattr(sys, "frozen", False):
        raise RuntimeError(
            "O motor de IA local (llama-cpp-python) não está incluído nesta "
            "versão empacotada."
        )
    if status_cb:
        status_cb("Instalando o motor de IA (wheel pronta, ~1 min)...")
    # 1ª tentativa: wheel pré-compilada de CPU (rápido, sem compilar).
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--prefer-binary",
         "--only-binary", ":all:", "--extra-index-url", _LLAMA_CPU_INDEX,
         "llama-cpp-python"],
        capture_output=True, text=True, timeout=1800, creationflags=_flags(),
    )
    if not llama_installed():
        # Fallback: deixa o pip resolver (pode baixar wheel do PyPI).
        if status_cb:
            status_cb("Baixando o motor de IA (alternativa)...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--prefer-binary",
             "llama-cpp-python"],
            capture_output=True, text=True, timeout=1800, creationflags=_flags(),
        )
    if not llama_installed():
        raise RuntimeError(
            "Não foi possível instalar o motor de IA local (llama-cpp-python). "
            "Verifique sua conexão. Detalhe: " + (r.stderr or "")[-300:]
        )


def load(key, n_ctx=8192):
    """Carrega o modelo em memória (uma vez) e devolve a instância Llama."""
    global _llm, _loaded_path
    path = model_path(key)
    if not path or not os.path.isfile(path):
        raise RuntimeError(
            "Modelo local não baixado. Baixe o modelo Gemma na aba IA."
        )
    if _llm is not None and _loaded_path == path:
        return _llm
    ensure_llama()
    from llama_cpp import Llama
    _llm = Llama(
        model_path=path,
        n_ctx=n_ctx,
        n_threads=max(2, (os.cpu_count() or 4)),
        verbose=False,
    )
    _loaded_path = path
    return _llm


def chat(key, system, messages, max_tokens=2048):
    """Gera resposta localmente. Gemma não tem 'system' separado, então o
    system é embutido na primeira mensagem do usuário."""
    llm = load(key)
    conv = list(messages)
    if system:
        if conv and conv[0].get("role") == "user":
            conv = [{"role": "user",
                     "content": f"{system}\n\n{conv[0]['content']}"}] + conv[1:]
        else:
            conv = [{"role": "user", "content": system}] + conv
    res = llm.create_chat_completion(
        messages=conv, temperature=0.3, max_tokens=max_tokens
    )
    return (res["choices"][0]["message"]["content"] or "").strip()


class GgufDownloadWorker(QThread):
    progress = pyqtSignal(int, int)   # 0..100
    status = pyqtSignal(str)
    finished_ok = pyqtSignal(str)     # key
    failed = pyqtSignal(str)

    def __init__(self, key, parent=None):
        super().__init__(parent)
        self.key = key

    def run(self):
        try:
            model = model_by_key(self.key)
            if not model:
                raise RuntimeError("Modelo desconhecido.")

            # 1) Instala o motor de IA primeiro (rápido: wheel pronta).
            self.progress.emit(0, 0)
            ensure_llama(status_cb=self.status.emit)

            # 2) Baixa o modelo (grande) com barra de progresso.
            dest = model_path(model)
            if os.path.isfile(dest) and os.path.getsize(dest) > 1_000_000:
                self.finished_ok.emit(self.key)
                return
            tmp = dest + ".part"
            self.status.emit(f"Baixando {model['label']} ({model['size']})...")
            headers = {"User-Agent": "Screvo/1.0"}
            with requests.get(model["url"], stream=True, timeout=60,
                              headers=headers) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0) or 0)
                done = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 512):
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            self.progress.emit(int(done / total * 100), 100)
            os.replace(tmp, dest)
            self.finished_ok.emit(self.key)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
