"""
FlowLayout — layout que quebra os widgets para a linha seguinte quando não
há espaço horizontal suficiente (baseado no exemplo oficial do Qt).

Usado para tornar as linhas de botões dos vídeos responsivas: em janelas
estreitas os botões descem para uma nova linha em vez de ficarem cortados.
"""

from PyQt6.QtCore import Qt, QRect, QSize, QPoint
from PyQt6.QtWidgets import QLayout, QSizePolicy, QWidget


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=6):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(),
                      margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self._spacing

        for item in self._items:
            item_w = item.sizeHint().width()
            item_h = item.sizeHint().height()
            next_x = x + item_w + spacing
            if next_x - spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + spacing
                next_x = x + item_w + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(item_w, item_h)))
            x = next_x
            line_height = max(line_height, item_h)

        return y + line_height - rect.y()


class FlowWidget(QWidget):
    """Widget que hospeda um FlowLayout e reporta corretamente heightForWidth."""

    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._flow = FlowLayout(self, margin=0, spacing=spacing)
        sp = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def add_widget(self, w):
        self._flow.addWidget(w)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._flow.heightForWidth(width)

    def sizeHint(self):
        return self._flow.sizeHint()

    def minimumSizeHint(self):
        return self._flow.minimumSize()
