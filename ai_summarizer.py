"""
Resumo de legendas usando um provedor de IA (Gemini, Claude, OpenAI, DeepSeek).

Envia o texto da legenda para a API do provedor selecionado e devolve o resumo.
A chamada roda em uma thread separada (QThread) para não travar a interface.
"""

import json
import requests

from PyQt6.QtCore import QThread, pyqtSignal


# Modelos padrão (usados quando o usuário não informa um nome de modelo).
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "claude": "claude-3-5-sonnet-20241022",
    "gemini": "gemini-1.5-flash",
    "deepseek": "deepseek-chat",
}

PROVIDER_LABELS = {
    "openai": "OpenAI",
    "claude": "Claude (Anthropic)",
    "gemini": "Google Gemini",
    "deepseek": "DeepSeek",
}

_SYSTEM_PROMPT = (
    "Você é um assistente que resume transcrições de reuniões e vídeos em "
    "português do Brasil.\n\n"
    "Responda SEMPRE em Markdown bem formatado, usando:\n"
    "- Títulos com ## e ###;\n"
    "- Um parágrafo de resumo geral;\n"
    "- Uma lista com os principais tópicos discutidos;\n"
    "- Uma seção de decisões tomadas (se houver);\n"
    "- Uma seção de itens de ação / tarefas em lista (se houver), indicando "
    "responsável quando mencionado.\n\n"
    "Use listas, negrito e tabelas quando ajudarem na clareza. Não inclua "
    "cercas de código (```) ao redor da resposta inteira; escreva o Markdown "
    "diretamente."
)


def _build_user_prompt(subtitle_text: str) -> str:
    return (
        "Resuma a transcrição a seguir.\n\n"
        "=== TRANSCRIÇÃO ===\n"
        f"{subtitle_text}\n"
        "=== FIM ==="
    )


def summarize(provider: str, model: str, api_key: str, subtitle_text: str,
              timeout: int = 120) -> str:
    """Chama o provedor de IA e devolve o texto do resumo.

    Lança exceção com mensagem amigável em caso de erro.
    """
    provider = (provider or "").strip().lower()
    api_key = (api_key or "").strip()
    model = (model or "").strip() or DEFAULT_MODELS.get(provider, "")

    if not api_key:
        raise ValueError(
            "Nenhuma API key configurada. Vá em IA e informe a chave do provedor."
        )
    if not subtitle_text.strip():
        raise ValueError("A legenda está vazia.")

    if provider == "openai":
        return _call_openai(model, api_key, subtitle_text, timeout)
    elif provider == "deepseek":
        return _call_openai(model, api_key, subtitle_text, timeout,
                            base_url="https://api.deepseek.com/v1/chat/completions")
    elif provider == "claude":
        return _call_claude(model, api_key, subtitle_text, timeout)
    elif provider == "gemini":
        return _call_gemini(model, api_key, subtitle_text, timeout)
    else:
        raise ValueError(f"Provedor desconhecido: {provider}")


def _call_openai(model, api_key, text, timeout,
                 base_url="https://api.openai.com/v1/chat/completions"):
    """OpenAI e DeepSeek compartilham o mesmo formato (chat completions)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(text)},
        ],
        "temperature": 0.3,
    }
    resp = requests.post(base_url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(_http_error(resp))
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _call_claude(model, api_key, text, timeout):
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 2048,
        "system": _SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": _build_user_prompt(text)},
        ],
    }
    resp = requests.post("https://api.anthropic.com/v1/messages",
                         headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(_http_error(resp))
    data = resp.json()
    parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    return "".join(parts).strip()


def _call_gemini(model, api_key, text, timeout):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    headers = {"Content-Type": "application/json"}
    payload = {
        "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
        "contents": [
            {"role": "user", "parts": [{"text": _build_user_prompt(text)}]}
        ],
        "generationConfig": {"temperature": 0.3},
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(_http_error(resp))
    data = resp.json()
    cand = data["candidates"][0]
    parts = cand["content"]["parts"]
    return "".join(p.get("text", "") for p in parts).strip()


def _http_error(resp) -> str:
    """Extrai uma mensagem de erro legível da resposta HTTP."""
    try:
        j = resp.json()
        msg = (
            j.get("error", {}).get("message")
            if isinstance(j.get("error"), dict)
            else j.get("error") or j.get("message")
        )
    except (ValueError, AttributeError):
        msg = resp.text[:300]
    return f"HTTP {resp.status_code}: {msg or 'erro desconhecido'}"


class SummarizeWorker(QThread):
    """Executa o resumo em background e emite o resultado."""
    finished_ok = pyqtSignal(str, str)   # (texto_resumo, caminho_video)
    failed = pyqtSignal(str, str)        # (mensagem_erro, caminho_video)

    def __init__(self, provider, model, api_key, subtitle_text, video_path, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.subtitle_text = subtitle_text
        self.video_path = video_path

    def run(self):
        try:
            summary = summarize(self.provider, self.model, self.api_key,
                                self.subtitle_text)
            self.finished_ok.emit(summary, self.video_path)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e), self.video_path)
