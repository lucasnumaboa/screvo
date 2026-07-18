"""
Janela de chat sobre um vídeo — pergunta e resposta usando a transcrição
como contexto, via o provedor de IA configurado.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextBrowser, QLineEdit
)
from PyQt6.QtCore import Qt

from ai_summarizer import ChatWorker

_MD_STYLE = """
    body { font-family: 'Segoe UI', sans-serif; color: #333; line-height: 1.5; }
    h1,h2,h3 { color: #C2185B; }
    code { background: #FFF0F5; color: #C2185B; padding: 1px 4px; border-radius: 4px; }
    table { border-collapse: collapse; }
    th, td { border: 1px solid #F0C8D6; padding: 4px 8px; }
"""


class ChatDialog(QDialog):
    def __init__(self, title, transcript, provider, model, api_key, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 640)
        self.setMinimumSize(420, 420)
        self.setStyleSheet("QDialog { background: #FAFAFA; }")

        self._transcript = transcript
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._history = []       # [{role, content}]
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QLabel(title)
        header.setStyleSheet("font-size: 16px; font-weight: 700; color: #FF69B4;")
        header.setWordWrap(True)
        layout.addWidget(header)

        self.log = QTextBrowser()
        self.log.setOpenExternalLinks(True)
        self.log.document().setDefaultStyleSheet(_MD_STYLE)
        self.log.setStyleSheet(
            "QTextBrowser { background: white; border: 1px solid #F0F0F0; "
            "border-radius: 12px; padding: 14px; font-size: 14px; color: #333; }"
        )
        layout.addWidget(self.log, 1)

        self._md = (
            "_Pergunte algo sobre o vídeo. As respostas usam a transcrição como "
            "contexto._\n\n"
        )
        self.log.setMarkdown(self._md)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Digite sua pergunta...")
        self.input.setStyleSheet(
            "QLineEdit { background: white; border: 1px solid #E8E8E8; "
            "border-radius: 8px; padding: 10px 12px; font-size: 13px; }"
            "QLineEdit:focus { border-color: #FF69B4; }"
        )
        self.input.returnPressed.connect(self._send)
        row.addWidget(self.input, 1)

        self.send_btn = QPushButton("Enviar")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet(
            "QPushButton { background: #FF69B4; border: none; border-radius: 8px; "
            "padding: 10px 20px; color: white; font-weight: 600; font-size: 13px; }"
            "QPushButton:hover { background: #FF91A4; }"
            "QPushButton:disabled { background: #F0B9CC; }"
        )
        self.send_btn.clicked.connect(self._send)
        row.addWidget(self.send_btn)
        layout.addLayout(row)

    def _append(self, who, text):
        self._md += f"**{who}:** {text}\n\n"
        self.log.setMarkdown(self._md)
        self.log.verticalScrollBar().setValue(
            self.log.verticalScrollBar().maximum()
        )

    def _send(self):
        question = self.input.text().strip()
        if not question or self._worker is not None:
            return
        self.input.clear()
        self._append("Você", question)
        self._append("IA", "_pensando..._")

        self.send_btn.setEnabled(False)
        self.input.setEnabled(False)

        self._worker = ChatWorker(
            self._provider, self._model, self._api_key,
            self._transcript, question, list(self._history)
        )
        self._pending_question = question
        self._worker.finished_ok.connect(self._on_answer)
        self._worker.failed.connect(self._on_error)
        self._worker.start()

    def _remove_thinking(self):
        # Remove o marcador "_pensando..._" da última linha
        self._md = self._md.replace("**IA:** _pensando..._\n\n", "")

    def _on_answer(self, answer):
        self._remove_thinking()
        self._append("IA", answer)
        self._history.append({"role": "user", "content": self._pending_question})
        self._history.append({"role": "assistant", "content": answer})
        self._reset_input()

    def _on_error(self, msg):
        self._remove_thinking()
        self._append("IA", f"⚠️ Erro: {msg}")
        self._reset_input()

    def _reset_input(self):
        self._worker = None
        self.send_btn.setEnabled(True)
        self.input.setEnabled(True)
        self.input.setFocus()
