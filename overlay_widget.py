"""
Overlay flutuante de gravação — barra minimalista sempre no topo.
Inspirado na barra do Handy (botões circulares, dots, fundo escuro translúcido).
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QGraphicsDropShadowEffect, QApplication
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    QPoint, pyqtSignal, QSize
)
from PyQt6.QtGui import QColor, QCursor
from styles import OVERLAY_STYLESHEET


class OverlayWidget(QWidget):
    """Barra flutuante de controle de gravação."""
    record_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    close_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(OVERLAY_STYLESHEET)

        self._recording = False
        self._paused = False
        self._drag_pos = None
        self._dot_index = 0

        self._setup_ui()
        self._setup_animations()

    def _setup_ui(self):
        # Container
        self.container = QWidget(self)
        self.container.setObjectName("overlayWidget")

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.addWidget(self.container)

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Botão Gravar/Pausar
        self.record_btn = QPushButton("⏺")
        self.record_btn.setProperty("class", "overlayBtn")
        self.record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.record_btn.setToolTip("Gravar")
        self.record_btn.clicked.connect(self._on_record)
        layout.addWidget(self.record_btn)

        # Dots animados
        self.dots = []
        for i in range(5):
            dot = QLabel("●")
            dot.setProperty("class", "overlayDot")
            dot.setStyleSheet("color: rgba(255, 105, 180, 0.3); font-size: 10px;")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setFixedWidth(12)
            layout.addWidget(dot)
            self.dots.append(dot)

        # Timer label
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setProperty("class", "overlayTimer")
        self.timer_label.setStyleSheet(
            "color: rgba(255,255,255,0.7); font-size: 13px; "
            "font-family: 'Consolas', monospace; font-weight: 600;"
        )
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setMinimumWidth(70)
        self.timer_label.hide()
        layout.addWidget(self.timer_label)

        # Botão Parar
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setProperty("class", "overlayBtn")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setToolTip("Parar")
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.hide()
        layout.addWidget(self.stop_btn)

        # Botão Fechar
        self.close_btn = QPushButton("✕")
        self.close_btn.setProperty("class", "overlayCloseBtn")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Fechar")
        self.close_btn.clicked.connect(self._on_close)
        layout.addWidget(self.close_btn)

        # Label "Salvando..."
        self.saving_label = QLabel("Salvando...")
        self.saving_label.setStyleSheet(
            "color: #FFB6C1; font-size: 13px; font-weight: 600; "
            "font-family: 'Segoe UI', sans-serif;"
        )
        self.saving_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.saving_label.hide()
        layout.addWidget(self.saving_label)

        # Timer para animar "Salvando..."
        self._saving_dots = 0
        self._saving_timer = QTimer()
        self._saving_timer.timeout.connect(self._animate_saving)
        self._saving_timer.setInterval(400)

        # Sombra
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        self.setFixedHeight(60)

    def _setup_animations(self):
        # Timer para dots animados
        self._dot_timer = QTimer()
        self._dot_timer.timeout.connect(self._animate_dots)
        self._dot_timer.setInterval(300)

        # Timer para atualizar tempo
        self._time_timer = QTimer()
        self._time_timer.timeout.connect(self._update_requested)
        self._time_timer.setInterval(1000)

    # Callback para atualizar tempo (será conectado externamente)
    _update_requested = pyqtSignal()

    def set_saving_state(self, saving):
        """Mostra estado 'Salvando...' no overlay."""
        if saving:
            self.record_btn.hide()
            self.stop_btn.hide()
            self.timer_label.hide()
            self.close_btn.hide()
            for dot in self.dots:
                dot.hide()
            self.saving_label.show()
            self._saving_dots = 0
            self._saving_timer.start()
            self._dot_timer.stop()
            self._time_timer.stop()
        else:
            self.saving_label.hide()
            self._saving_timer.stop()
            self.close_btn.show()

    def _animate_saving(self):
        """Anima os pontos de 'Salvando...'"""
        self._saving_dots = (self._saving_dots + 1) % 4
        dots = "." * self._saving_dots
        self.saving_label.setText(f"Salvando{dots}")

    def set_recording_state(self, recording, paused=False):
        """Atualiza visual do overlay."""
        self._recording = recording
        self._paused = paused

        # Garante que saving state está desligado
        self.saving_label.hide()
        self._saving_timer.stop()
        self.close_btn.show()
        self.record_btn.show()

        if recording:
            self.record_btn.setText("⏸" if not paused else "▶")
            self.record_btn.setToolTip("Pausar" if not paused else "Continuar")
            self.record_btn.setProperty("recording", "true")
            self.stop_btn.show()
            self.timer_label.show()

            for dot in self.dots:
                dot.hide()

            if not paused:
                self._dot_timer.start()
            else:
                self._dot_timer.stop()

            self._time_timer.start()
        else:
            self.record_btn.setText("⏺")
            self.record_btn.setToolTip("Gravar")
            self.record_btn.setProperty("recording", "false")
            self.stop_btn.hide()
            self.timer_label.hide()
            self.timer_label.setText("00:00:00")

            for dot in self.dots:
                dot.show()
                dot.setStyleSheet("color: rgba(255, 105, 180, 0.3); font-size: 10px;")

            self._dot_timer.stop()
            self._time_timer.stop()

        # Force style refresh
        self.record_btn.style().unpolish(self.record_btn)
        self.record_btn.style().polish(self.record_btn)

    def update_time(self, time_str):
        """Atualiza display de tempo."""
        self.timer_label.setText(time_str)

    def _animate_dots(self):
        """Animação dos dots durante gravação."""
        if not self._recording:
            return

        colors = [
            "rgba(255, 105, 180, 0.3)",
            "rgba(255, 105, 180, 0.5)",
            "rgba(255, 105, 180, 0.8)",
            "#FF69B4",
            "rgba(255, 105, 180, 0.8)",
        ]

        # Os dots ficam escondidos durante gravação, esta animação
        # é para o indicador de recording (pulsing no botão)
        pass

    def _on_record(self):
        if self._recording:
            self.pause_clicked.emit()
        else:
            self.record_clicked.emit()

    def _on_stop(self):
        self.stop_clicked.emit()

    def _on_close(self):
        self.close_clicked.emit()

    def show_at_position(self, position="bottom"):
        """Mostra overlay na posição configurada."""
        self.adjustSize()
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2

            if position == "bottom":
                y = geo.y() + geo.height() - self.height() - 40
            else:
                y = geo.y() + 40

            self.move(x, y)

        self.show()
        self.raise_()

    # Drag support
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
