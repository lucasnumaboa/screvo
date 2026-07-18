"""
Integração com provedores de IA (Gemini, Claude, OpenAI, DeepSeek).

Usado para:
- resumir legendas (com templates de formato);
- responder perguntas sobre a transcrição (chat).

As chamadas de rede rodam em QThreads para não travar a interface.
"""

import requests

from PyQt6.QtCore import QThread, pyqtSignal


# Modelos padrão (usados quando o usuário não informa um nome de modelo).
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "claude": "claude-3-5-sonnet-20241022",
    "gemini": "gemini-1.5-flash",
    "deepseek": "deepseek-chat",
    "local": "gemma2-2b",
}

PROVIDER_LABELS = {
    "openai": "OpenAI",
    "claude": "Claude (Anthropic)",
    "gemini": "Google Gemini",
    "deepseek": "DeepSeek",
    "local": "IA local (no app)",
}

_SUMMARY_SYSTEM = (
    "Você é um assistente que resume transcrições de reuniões e vídeos em "
    "português do Brasil.\n\n"
    "Responda SEMPRE em Markdown bem formatado (títulos com ## e ###, listas, "
    "negrito e tabelas quando ajudarem). Não envolva a resposta inteira em "
    "cercas de código."
)

_SUMMARY_DEFAULT_BODY = (
    "Gere: um parágrafo de resumo geral, uma lista com os principais tópicos, "
    "e (se houver) seções de decisões tomadas e itens de ação."
)

_CHAT_SYSTEM = (
    "Você é um assistente que responde perguntas sobre o conteúdo de um vídeo, "
    "com base na transcrição fornecida. Responda em português do Brasil, de "
    "forma objetiva e em Markdown quando fizer sentido. Se a resposta não "
    "estiver na transcrição, diga que não foi possível encontrar essa "
    "informação no vídeo.\n\n"
    "=== TRANSCRIÇÃO DO VÍDEO ===\n{transcript}\n=== FIM DA TRANSCRIÇÃO ==="
)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def summarize(provider, model, api_key, subtitle_text, template_instructions="",
              timeout=120):
    """Resume a transcrição; template_instructions ajusta o formato."""
    _validate(provider, api_key)
    if not subtitle_text.strip():
        raise ValueError("A legenda está vazia.")

    system = _SUMMARY_SYSTEM
    body = template_instructions.strip() or _SUMMARY_DEFAULT_BODY
    user = (
        f"{body}\n\n=== TRANSCRIÇÃO ===\n{subtitle_text}\n=== FIM ==="
    )
    return _dispatch(provider, model, api_key, system,
                     [{"role": "user", "content": user}], timeout)


_REPORT_SYSTEM = (
    "Você é um analista que produz um RELATÓRIO COMPLETO em português do Brasil "
    "a partir de um vídeo, usando a TRANSCRIÇÃO (com tempos) e o TEXTO DA TELA "
    "(OCR, com tempos) fornecidos.\n\n"
    "Escreva em Markdown bem estruturado: título, resumo executivo, seções "
    "cronológicas descrevendo o que acontece, decisões e itens de ação.\n\n"
    "FERRAMENTA DE CAPTURA: você pode inserir capturas de tela do vídeo no corpo "
    "do relatório. Para isso, escreva um marcador SOZINHO em uma linha, no "
    "formato:\n"
    "  [[FRAME:mm:ss]]\n"
    "onde mm:ss (ou segundos) é um momento relevante presente na transcrição/OCR. "
    "Você também pode recortar a imagem (opcional) usando "
    "[[FRAME:mm:ss|crop=x,y,w,h]] em pixels — mas prefira o frame inteiro, pois "
    "você não vê a imagem. Insira uma captura logo após descrever o momento que "
    "ela ilustra. Use no máximo cerca de 8 capturas, apenas em momentos que "
    "realmente ajudem. Não invente tempos maiores que a duração do vídeo."
)


def generate_report(provider, model, api_key, context, timeout=240):
    """Gera um relatório completo em Markdown com marcadores [[FRAME:...]]."""
    _validate(provider, api_key)
    return _dispatch(provider, model, api_key, _REPORT_SYSTEM,
                     [{"role": "user", "content": context}], timeout)


def chat_answer(provider, model, api_key, transcript, question, history=None,
                timeout=120):
    """Responde a uma pergunta sobre a transcrição, considerando o histórico."""
    _validate(provider, api_key)
    system = _CHAT_SYSTEM.format(transcript=transcript.strip())
    messages = list(history or [])
    messages.append({"role": "user", "content": question})
    return _dispatch(provider, model, api_key, system, messages, timeout)


# ---------------------------------------------------------------------------
# Internos
# ---------------------------------------------------------------------------
def _validate(provider, api_key):
    if not (provider or "").strip():
        raise ValueError("Nenhum provedor de IA selecionado (aba IA).")
    # A IA local roda no app e não usa API key.
    if provider.strip().lower() == "local":
        return
    if not (api_key or "").strip():
        raise ValueError("Nenhuma API key configurada (aba IA).")


def _dispatch(provider, model, api_key, system, messages, timeout):
    provider = provider.strip().lower()
    model = (model or "").strip() or DEFAULT_MODELS.get(provider, "")
    api_key = api_key.strip()

    if provider == "openai":
        return _call_openai(model, api_key, system, messages, timeout)
    elif provider == "deepseek":
        return _call_openai(model, api_key, system, messages, timeout,
                            base_url="https://api.deepseek.com/v1/chat/completions")
    elif provider == "claude":
        return _call_claude(model, api_key, system, messages, timeout)
    elif provider == "gemini":
        return _call_gemini(model, api_key, system, messages, timeout)
    elif provider == "local":
        return _call_local(model, system, messages)
    raise ValueError(f"Provedor desconhecido: {provider}")


def _call_local(model, system, messages):
    """IA local rodando no próprio app (llama.cpp / GGUF). Sem API key."""
    import local_llm
    return local_llm.chat(model, system, messages)


def _call_openai(model, api_key, system, messages, timeout,
                 base_url="https://api.openai.com/v1/chat/completions"):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages,
        "temperature": 0.3,
    }
    resp = requests.post(base_url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(_http_error(resp))
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_claude(model, api_key, system, messages, timeout):
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 2048,
        "system": system,
        "messages": messages,
    }
    resp = requests.post("https://api.anthropic.com/v1/messages",
                         headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(_http_error(resp))
    data = resp.json()
    parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    return "".join(parts).strip()


def _call_gemini(model, api_key, system, messages, timeout):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.3},
    }
    resp = requests.post(url, headers={"Content-Type": "application/json"},
                         json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(_http_error(resp))
    cand = resp.json()["candidates"][0]
    return "".join(p.get("text", "") for p in cand["content"]["parts"]).strip()


def _http_error(resp):
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


# ---------------------------------------------------------------------------
# Workers (QThread)
# ---------------------------------------------------------------------------
class SummarizeWorker(QThread):
    finished_ok = pyqtSignal(str, str)   # (resumo, caminho_video)
    failed = pyqtSignal(str, str)        # (erro, caminho_video)

    def __init__(self, provider, model, api_key, subtitle_text, video_path,
                 template_instructions="", parent=None):
        super().__init__(parent)
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.subtitle_text = subtitle_text
        self.video_path = video_path
        self.template_instructions = template_instructions

    def run(self):
        try:
            summary = summarize(self.provider, self.model, self.api_key,
                                self.subtitle_text, self.template_instructions)
            self.finished_ok.emit(summary, self.video_path)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e), self.video_path)


class ChatWorker(QThread):
    finished_ok = pyqtSignal(str)   # resposta
    failed = pyqtSignal(str)        # erro

    def __init__(self, provider, model, api_key, transcript, question,
                 history=None, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.transcript = transcript
        self.question = question
        self.history = history or []

    def run(self):
        try:
            answer = chat_answer(self.provider, self.model, self.api_key,
                                 self.transcript, self.question, self.history)
            self.finished_ok.emit(answer)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
