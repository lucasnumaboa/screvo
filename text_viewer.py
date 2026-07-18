"""
Janela para visualizar legendas e resumos dentro do app.

Renderiza Markdown de forma bonita (títulos, listas, tabelas) ou texto puro.
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser, QPushButton, QLabel,
    QApplication, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer


_MD_STYLE = """
    body { font-family: 'Segoe UI', sans-serif; color: #333; line-height: 1.55; }
    h1, h2, h3 { color: #C2185B; margin-top: 14px; margin-bottom: 6px; }
    h1 { font-size: 20px; }
    h2 { font-size: 17px; }
    h3 { font-size: 15px; }
    p { margin: 6px 0; }
    ul, ol { margin: 6px 0 6px 18px; }
    li { margin: 3px 0; }
    strong { color: #222; }
    code { background: #FFF0F5; color: #C2185B; padding: 1px 4px; border-radius: 4px; }
    table { border-collapse: collapse; margin: 8px 0; }
    th, td { border: 1px solid #F0C8D6; padding: 6px 10px; }
    th { background: #FFF0F5; color: #C2185B; }
    a { color: #FF69B4; }
"""


class TextViewerDialog(QDialog):
    """Diálogo simples que exibe texto ou Markdown formatado."""

    def __init__(self, title, content, is_markdown=False, file_path=None,
                 parent=None, base_dir=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 640)
        self.setMinimumSize(420, 360)
        self._file_path = file_path
        self._raw_content = content
        self._base_dir = base_dir or (
            os.path.dirname(file_path) if file_path else None
        )
        self.setStyleSheet("QDialog { background: #FAFAFA; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel(title)
        header.setStyleSheet("font-size: 16px; font-weight: 700; color: #FF69B4;")
        header.setWordWrap(True)
        layout.addWidget(header)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet(
            "QTextBrowser { background: white; border: 1px solid #F0F0F0; "
            "border-radius: 12px; padding: 16px; font-size: 14px; color: #333; }"
        )
        if is_markdown:
            if self._base_dir:
                self.browser.setSearchPaths([self._base_dir])
            self.browser.document().setDefaultStyleSheet(_MD_STYLE)
            self.browser.setMarkdown(content)
        else:
            self.browser.setPlainText(content)
        layout.addWidget(self.browser, 1)

        # Botões
        btn_row = QHBoxLayout()

        self.copy_btn = QPushButton("📋  Copiar conteúdo")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setStyleSheet(
            "QPushButton { background: #EDE7F6; border: 1px solid #B39DDB; "
            "border-radius: 8px; padding: 8px 18px; font-size: 13px; "
            "color: #5E35B1; font-weight: 600; }"
            "QPushButton:hover { background: #D1C4E9; }"
        )
        self.copy_btn.clicked.connect(self._copy_content)
        btn_row.addWidget(self.copy_btn)

        self.export_btn = QPushButton("⤓  Exportar")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.setStyleSheet(
            "QPushButton { background: #E3F2FD; border: 1px solid #90CAF9; "
            "border-radius: 8px; padding: 8px 18px; font-size: 13px; "
            "color: #1565C0; font-weight: 600; }"
            "QPushButton:hover { background: #BBDEFB; }"
        )
        self.export_btn.clicked.connect(self._export)
        btn_row.addWidget(self.export_btn)

        btn_row.addStretch()

        if file_path:
            open_btn = QPushButton("Abrir arquivo")
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.setStyleSheet(
                "QPushButton { background: #F5F5F5; border: 1px solid #E8E8E8; "
                "border-radius: 8px; padding: 8px 18px; font-size: 13px; }"
                "QPushButton:hover { background: #FFE4E9; border-color: #FFB6C1; }"
            )
            open_btn.clicked.connect(self._open_external)
            btn_row.addWidget(open_btn)

        close_btn = QPushButton("Fechar")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: #FF69B4; border: none; border-radius: 8px; "
            "padding: 8px 22px; color: white; font-weight: 600; font-size: 13px; }"
            "QPushButton:hover { background: #FF91A4; }"
        )
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _copy_content(self):
        """Copia o conteúdo (texto/Markdown bruto) para a área de transferência."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._raw_content)
        self.copy_btn.setText("✓  Copiado!")
        QTimer.singleShot(
            1800, lambda: self.copy_btn.setText("📋  Copiar conteúdo")
        )

    def _export(self):
        """Exporta o conteúdo para .md, .docx ou .pdf."""
        base = "resumo"
        start_dir = ""
        if self._file_path:
            base = os.path.splitext(os.path.basename(self._file_path))[0]
            start_dir = os.path.dirname(self._file_path)
        default = os.path.join(start_dir, base + ".md") if start_dir else base + ".md"

        path, selected = QFileDialog.getSaveFileName(
            self, "Exportar", default,
            "Markdown (*.md);;Documento Word (*.docx);;PDF (*.pdf)"
        )
        if not path:
            return

        # Garante a extensão de acordo com o filtro escolhido
        ext_map = {"Markdown": ".md", "Word": ".docx", "PDF": ".pdf"}
        for key, ext in ext_map.items():
            if key in selected and not path.lower().endswith(ext):
                path += ext
                break

        try:
            import exporters
            self.export_btn.setText("Exportando...")
            self.export_btn.setEnabled(False)
            QApplication.processEvents()
            exporters.export(self._raw_content, path, base_dir=self._base_dir)
            self.export_btn.setText("✓  Exportado!")
            QTimer.singleShot(2000, lambda: self.export_btn.setText("⤓  Exportar"))
        except Exception as e:
            QMessageBox.critical(self, "Erro ao exportar", str(e))
            self.export_btn.setText("⤓  Exportar")
        finally:
            self.export_btn.setEnabled(True)

    def _open_external(self):
        if self._file_path and os.path.isfile(self._file_path):
            try:
                os.startfile(self._file_path)
            except Exception:
                pass
