"""
Toggle switch customizado estilo iOS/Handy — rosa quando ativo.
"""

from PyQt6.QtWidgets import QWidget, QAbstractButton, QSizePolicy
from PyQt6.QtCore import Qt, QRect, QSize, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush


class ToggleSwitch(QAbstractButton):
    """Toggle switch estilizado rosa."""

    def __init__(self, parent=None, checked=False):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._handle_position = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"handlePosition")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.toggled.connect(self._on_toggled)

    @pyqtProperty(float)
    def handlePosition(self):
        return self._handle_position

    @handlePosition.setter
    def handlePosition(self, pos):
        self._handle_position = pos
        self.update()

    def _on_toggled(self, checked):
        self._anim.stop()
        self._anim.setStartValue(self._handle_position)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def sizeHint(self):
        return QSize(48, 26)

    def hitButton(self, pos):
        return self.contentsRect().contains(pos)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        radius = h / 2

        # Track
        if self.isChecked() or self._handle_position > 0:
            # Interpolar entre cinza e rosa
            t = self._handle_position
            r = int(220 + (255 - 220) * t)
            g = int(220 + (105 - 220) * t)
            b = int(220 + (180 - 220) * t)
            track_color = QColor(r, g, b)
        else:
            track_color = QColor(220, 220, 220)

        p.setBrush(QBrush(track_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, radius, radius)

        # Handle
        handle_margin = 3
        handle_size = h - 2 * handle_margin
        handle_x = handle_margin + self._handle_position * (w - handle_size - 2 * handle_margin)

        # Handle shadow
        shadow_color = QColor(0, 0, 0, 30)
        p.setBrush(QBrush(shadow_color))
        p.drawEllipse(
            int(handle_x), handle_margin + 1,
            int(handle_size), int(handle_size)
        )

        # Handle body
        p.setBrush(QBrush(QColor(255, 255, 255)))
        p.drawEllipse(
            int(handle_x), handle_margin,
            int(handle_size), int(handle_size)
        )

        p.end()
