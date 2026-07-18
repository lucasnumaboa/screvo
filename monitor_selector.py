"""
Seletor de monitor estilo Microsoft Teams — thumbnails das telas e lista de janelas.
"""

import ctypes
import ctypes.wintypes
from PIL import ImageGrab
import io
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGraphicsDropShadowEffect, QApplication,
    QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QPixmap, QImage, QColor, QPainter, QIcon
from styles import MONITOR_SELECTOR_STYLESHEET
from recorder import Recorder


# --- Windows API para enumerar janelas ---
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
IsWindowVisible = user32.IsWindowVisible
GetWindowLong = user32.GetWindowLongW
GetWindowRect = user32.GetWindowRect
IsIconic = user32.IsIconic
GetWindowThreadProcessId = user32.GetWindowThreadProcessId

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
GWL_STYLE = -16
WS_VISIBLE = 0x10000000


def get_open_windows():
    """Retorna lista de janelas abertas com título e rect."""
    windows = []

    def enum_handler(hwnd, lParam):
        if not IsWindowVisible(hwnd):
            return True

        length = GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        title = ctypes.create_unicode_buffer(length + 1)
        GetWindowTextW(hwnd, title, length + 1)
        title_str = title.value

        # Filtra janelas de sistema
        if not title_str or title_str in ("Program Manager", "Windows Input Experience",
                                           "MSCTFIME UI", "Default IME", ""):
            return True

        # Filtra janelas tool
        ex_style = GetWindowLong(hwnd, GWL_EXSTYLE)
        if (ex_style & WS_EX_TOOLWINDOW) and not (ex_style & WS_EX_APPWINDOW):
            return True

        # Pega dimensões
        rect = ctypes.wintypes.RECT()
        GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w < 100 or h < 50:
            return True

        windows.append({
            "hwnd": hwnd,
            "title": title_str,
            "x": rect.left,
            "y": rect.top,
            "width": w,
            "height": h,
            "is_minimized": bool(IsIconic(hwnd)),
        })
        return True

    EnumWindows(EnumWindowsProc(enum_handler), 0)
    return windows


def capture_monitor_thumbnail(monitor_index, monitors, thumb_size=(280, 158)):
    """Captura screenshot de um monitor e retorna QPixmap thumbnail."""
    try:
        if monitor_index < len(monitors):
            m = monitors[monitor_index]
            bbox = (m["x"], m["y"], m["x"] + m["width"], m["y"] + m["height"])
            img = ImageGrab.grab(bbox=bbox, all_screens=True)
        else:
            img = ImageGrab.grab(all_screens=True)

        # Converte para QPixmap
        img = img.resize(thumb_size)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        pixmap = QPixmap()
        pixmap.loadFromData(img_bytes.read())
        return pixmap
    except Exception:
        # Retorna placeholder
        pixmap = QPixmap(thumb_size[0], thumb_size[1])
        pixmap.fill(QColor(40, 40, 40))
        return pixmap


def capture_all_screens_thumbnail(thumb_size=(280, 158)):
    """Captura screenshot de todas as telas juntas."""
    try:
        img = ImageGrab.grab(all_screens=True)
        img.thumbnail(thumb_size)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        pixmap = QPixmap()
        pixmap.loadFromData(img_bytes.read())
        return pixmap
    except Exception:
        pixmap = QPixmap(thumb_size[0], thumb_size[1])
        pixmap.fill(QColor(40, 40, 40))
        return pixmap


class ScreenThumbnail(QPushButton):
    """Card de thumbnail de tela clicável."""

    def __init__(self, pixmap, label_text, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(268, 190)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)

        # Thumbnail
        img_label = QLabel()
        img_label.setPixmap(pixmap.scaled(
            258, 145,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setStyleSheet(
            "border-radius: 8px; background: #1a1a1a; padding: 2px;"
        )
        layout.addWidget(img_label)

        # Label
        name = QLabel(label_text)
        name.setStyleSheet("color: white; font-size: 12px; font-weight: 500;")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)

        self.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.03);
                border: 2px solid transparent;
                border-radius: 12px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.08);
                border-color: rgba(255,105,180,0.3);
            }
            QPushButton:checked {
                background: rgba(255,105,180,0.12);
                border-color: #FF69B4;
            }
        """)


class WindowItem(QPushButton):
    """Item de janela na lista."""

    def __init__(self, title, resolution, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Ícone genérico
        icon_label = QLabel("🪟")
        icon_label.setStyleSheet("font-size: 20px;")
        icon_label.setFixedWidth(30)
        layout.addWidget(icon_label)

        # Título + resolução
        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)

        title_label = QLabel(title[:60] + ("..." if len(title) > 60 else ""))
        title_label.setStyleSheet("color: white; font-size: 13px; font-weight: 500;")
        text_layout.addWidget(title_label)

        res_label = QLabel(resolution)
        res_label.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 11px;")
        text_layout.addWidget(res_label)

        layout.addLayout(text_layout, 1)

        self.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.03);
                border: 1px solid transparent;
                border-radius: 10px;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.08);
                border-color: rgba(255,105,180,0.2);
            }
            QPushButton:checked {
                background: rgba(255,105,180,0.12);
                border-color: #FF69B4;
            }
        """)


class MonitorSelector(QWidget):
    """Dialog de seleção estilo Teams."""
    monitor_selected = pyqtSignal(list)  # lista de índices (-1 = todas)
    window_selected = pyqtSignal(int)    # hwnd da janela
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.selected_monitors = set()   # índices de telas selecionadas
        self.selected_window = None      # hwnd (exclusivo)
        self._screen_buttons = {}        # index -> botão
        self._window_buttons = []        # (hwnd, botão)
        self._setup_ui()

    def _setup_ui(self):
        self.container = QWidget(self)
        self.container.setObjectName("monitorSelector")
        self.container.setStyleSheet("""
            #monitorSelector {
                background-color: rgba(28, 28, 28, 245);
                border-radius: 16px;
                border: 1px solid rgba(255,255,255,0.1);
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.addWidget(self.container)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Selecionar Conteúdo")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()

        # Botão fechar
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: rgba(255,255,255,0.5); font-size: 16px;
                border-radius: 16px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.1); color: white; }
        """)
        close_btn.clicked.connect(self._cancel)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(500)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: transparent; width: 6px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.2); border-radius: 3px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(12)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Botões de ação
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: 1px solid rgba(255,255,255,0.2);
                border-radius: 8px; padding: 10px 24px; color: rgba(255,255,255,0.7);
                font-size: 13px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.1); }
        """)
        cancel_btn.clicked.connect(self._cancel)
        btn_layout.addWidget(cancel_btn)

        self.start_btn = QPushButton("▶  Gravar")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF69B4, stop:1 #FF91A4);
                border: none; border-radius: 8px; padding: 10px 28px;
                color: white; font-size: 14px; font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF91A4, stop:1 #FFB6C1);
            }
            QPushButton:disabled {
                background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.3);
            }
        """)
        self.start_btn.clicked.connect(self._start)
        btn_layout.addWidget(self.start_btn)

        layout.addLayout(btn_layout)

        # Sombra
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 8)
        self.container.setGraphicsEffect(shadow)

    def populate(self):
        """Popula com screenshots e janelas."""
        # Limpa conteúdo anterior
        self._screen_buttons = {}
        self._window_buttons = []
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        self.selected_monitors = set()
        self.selected_window = None
        self.start_btn.setEnabled(False)

        # === TELAS ===
        screens_label = QLabel("Telas (selecione uma ou mais)")
        screens_label.setStyleSheet(
            "color: rgba(255,255,255,0.6); font-size: 13px; font-weight: 600; padding: 4px 0;"
        )
        self.scroll_layout.addWidget(screens_label)

        screens_grid = QHBoxLayout()
        screens_grid.setSpacing(12)

        monitors = Recorder.list_monitors()

        for m in monitors:
            pixmap = capture_monitor_thumbnail(m["index"], monitors)
            primary = " ⭐" if m.get("is_primary") else ""
            label = f"Tela {m['index'] + 1}{primary}  ({m['width']}×{m['height']})"
            thumb = ScreenThumbnail(pixmap, label)
            idx = m["index"]
            thumb.clicked.connect(lambda checked, i=idx: self._toggle_monitor(i))
            screens_grid.addWidget(thumb)
            self._screen_buttons[idx] = thumb

        screens_grid.addStretch()
        self.scroll_layout.addLayout(screens_grid)

        # === JANELAS ===
        windows = get_open_windows()
        if windows:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background: rgba(255,255,255,0.08);")
            self.scroll_layout.addWidget(sep)

            win_label = QLabel(f"Janela ({len(windows)})")
            win_label.setStyleSheet(
                "color: rgba(255,255,255,0.6); font-size: 13px; font-weight: 600; padding: 4px 0;"
            )
            self.scroll_layout.addWidget(win_label)

            for w in windows[:15]:  # Limita a 15
                res = f"{w['width']}×{w['height']}"
                if w["is_minimized"]:
                    res += " (minimizada)"
                item = WindowItem(w["title"], res)
                hwnd = w["hwnd"]
                item.clicked.connect(lambda checked, h=hwnd, btn=item: self._select_window(h, btn))
                self.scroll_layout.addWidget(item)
                self._window_buttons.append((hwnd, item))

        self.scroll_layout.addStretch()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _toggle_monitor(self, index):
        """Alterna a seleção de uma tela (permite uma ou várias)."""
        # Selecionar tela cancela seleção de janela (são exclusivos)
        if self.selected_window is not None:
            self.selected_window = None
            for _, b in self._window_buttons:
                b.setChecked(False)

        if index in self.selected_monitors:
            self.selected_monitors.discard(index)
        else:
            self.selected_monitors.add(index)

        # Reflete o estado visual (checked) de cada thumbnail
        for i, btn in self._screen_buttons.items():
            btn.setChecked(i in self.selected_monitors)

        self.start_btn.setEnabled(
            bool(self.selected_monitors) or self.selected_window is not None
        )

    def _select_window(self, hwnd, btn):
        """Seleciona uma janela (exclusivo — desmarca telas e outras janelas)."""
        self.selected_monitors = set()
        for b in self._screen_buttons.values():
            b.setChecked(False)

        self.selected_window = hwnd
        for _, b in self._window_buttons:
            b.setChecked(b is btn)

        self.start_btn.setEnabled(True)

    def _start(self):
        # Esconde a janela ANTES de iniciar a gravação. O start pode levar
        # um instante (enumeração de dispositivos), então fechamos primeiro
        # para a janela sumir imediatamente ao clicar em "Gravar".
        self.hide()
        QApplication.processEvents()
        if self.selected_window is not None:
            self.window_selected.emit(self.selected_window)
        elif self.selected_monitors:
            self.monitor_selected.emit(sorted(self.selected_monitors))

    def _cancel(self):
        self.cancelled.emit()
        self.hide()

    def show_centered(self):
        """Mostra centralizado."""
        self.populate()
        self.setFixedWidth(640)
        self.adjustSize()

        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)

        self.show()
        self.raise_()
        self.activateWindow()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        super().keyPressEvent(event)
