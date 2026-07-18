"""
Barra de controle de áudio embutida na linha do vídeo.

NÃO possui player próprio: apenas controla o player ÚNICO que vive na janela
(SettingsWindow). Assim o áudio continua tocando mesmo quando a lista é
recriada (ex.: ao criar legenda) ou quando você troca de aba — e destruir as
linhas nunca mexe no motor de mídia (o que travava o app).
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSlider, QLabel
from PyQt6.QtCore import Qt


class AudioPlayerBar(QWidget):
    def __init__(self, video_path, owner, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.owner = owner

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        self.play_btn = QPushButton("▶  Ouvir áudio")
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet(
            "QPushButton { background: #FFF8E1; border: 1px solid #FFE082; "
            "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
            "color: #F57F17; font-weight: 600; }"
            "QPushButton:hover { background: #FFECB3; }"
        )
        self.play_btn.clicked.connect(
            lambda: self.owner.play_audio_toggle(self, self.video_path)
        )
        layout.addWidget(self.play_btn)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setStyleSheet(
            "QSlider::groove:horizontal { background: #EEE; height: 4px; border-radius: 2px; }"
            "QSlider::handle:horizontal { background: #FF69B4; width: 12px; height: 12px; "
            "margin: -4px 0; border-radius: 6px; }"
            "QSlider::sub-page:horizontal { background: #FFB6C1; border-radius: 2px; }"
        )
        self.slider.sliderMoved.connect(lambda pos: self.owner.audio_seek(pos))
        layout.addWidget(self.slider, 1)

        self.time = QLabel("00:00 / 00:00")
        self.time.setStyleSheet("color: #999; font-size: 11px; font-family: Consolas;")
        layout.addWidget(self.time)

        # Se esta faixa já é a que está tocando (lista recriada), reflete o estado
        self.owner.bind_existing_audio(self, video_path)

    # Métodos chamados pelo dono (SettingsWindow)
    def set_playing(self, playing):
        self.play_btn.setText("⏸  Pausar" if playing else "▶  Ouvir áudio")

    def set_range(self, dur):
        self.slider.setRange(0, dur)

    def set_position(self, pos, dur):
        self.slider.blockSignals(True)
        self.slider.setValue(pos)
        self.slider.blockSignals(False)
        self.time.setText(f"{self._fmt(pos)} / {self._fmt(dur)}")

    @staticmethod
    def _fmt(ms):
        s = max(0, ms) // 1000
        return f"{s // 60:02d}:{s % 60:02d}"
