"""
Seletor de região da tela — overlay em tela cheia onde o usuário arrasta um
retângulo. Emite region_selected((x, y, w, h)) em coordenadas globais.
"""

from PyQt6.QtWidgets import QWidget, QApplication, QLabel
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen


class RegionSelector(QWidget):
    region_selected = pyqtSignal(tuple)   # (x, y, w, h) em coordenadas globais
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._origin = None
        self._rect = QRect()

        self.hint = QLabel(
            "Arraste para selecionar a região  •  Enter confirma  •  Esc cancela",
            self,
        )
        self.hint.setStyleSheet(
            "color: white; background: rgba(255,105,180,0.85); "
            "padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 600;"
        )
        self.hint.adjustSize()

    def start(self):
        """Cobre toda a área virtual (todos os monitores) e aparece."""
        vgeo = self._virtual_geometry()
        self._offset = vgeo.topLeft()
        self.setGeometry(vgeo)
        self._rect = QRect()
        self._origin = None
        self.hint.move(30, 30)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def _virtual_geometry(self):
        rect = QRect()
        for screen in QApplication.screens():
            rect = rect.united(screen.geometry())
        return rect

    # ---- pintura ----
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))
        if not self._rect.isNull():
            # "Fura" a área selecionada (mostra a tela nítida)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_Clear
            )
            painter.fillRect(self._rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            pen = QPen(QColor("#FF69B4"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(self._rect)

            size = f"{self._rect.width()} × {self._rect.height()}"
            painter.setPen(QColor("white"))
            painter.drawText(self._rect.adjusted(4, -20, 0, 0).topLeft(), size)

    # ---- mouse ----
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._rect = QRect(self._origin, self._origin)
            self.update()

    def mouseMoveEvent(self, event):
        if self._origin is not None:
            self._rect = QRect(self._origin, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._origin is not None:
            self._origin = None
            self.update()

    # ---- teclado ----
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._confirm()

    def mouseDoubleClickEvent(self, event):
        self._confirm()

    def _confirm(self):
        if self._rect.width() > 10 and self._rect.height() > 10:
            gx = self._rect.x() + self._offset.x()
            gy = self._rect.y() + self._offset.y()
            w = self._rect.width() - (self._rect.width() % 2)
            h = self._rect.height() - (self._rect.height() % 2)
            self.hide()
            self.region_selected.emit((gx, gy, w, h))
        else:
            self.hide()
            self.cancelled.emit()
