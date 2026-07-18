"""
Mini-player de áudio embutido na linha do vídeo.

Toca o áudio direto do arquivo de vídeo (sem gerar arquivo). O QMediaPlayer é
criado só no primeiro play, para não pesar quando há muitos vídeos na lista.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSlider, QLabel
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput


class AudioPlayerBar(QWidget):
    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self._player = None
        self._audio = None

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
        self.play_btn.clicked.connect(self._toggle)
        layout.addWidget(self.play_btn)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setEnabled(False)
        self.slider.setStyleSheet(
            "QSlider::groove:horizontal { background: #EEE; height: 4px; border-radius: 2px; }"
            "QSlider::handle:horizontal { background: #FF69B4; width: 12px; height: 12px; "
            "margin: -4px 0; border-radius: 6px; }"
            "QSlider::sub-page:horizontal { background: #FFB6C1; border-radius: 2px; }"
        )
        self.slider.sliderMoved.connect(self._seek)
        layout.addWidget(self.slider, 1)

        self.time = QLabel("00:00 / 00:00")
        self.time.setStyleSheet("color: #999; font-size: 11px; font-family: Consolas;")
        layout.addWidget(self.time)

    def _ensure_player(self):
        if self._player is None:
            self._player = QMediaPlayer()
            self._audio = QAudioOutput()
            self._player.setAudioOutput(self._audio)
            self._player.setSource(QUrl.fromLocalFile(self.video_path))
            self._player.positionChanged.connect(self._on_pos)
            self._player.durationChanged.connect(self._on_dur)
            self._player.playbackStateChanged.connect(self._on_state)
            self.slider.setEnabled(True)

    def _toggle(self):
        self._ensure_player()
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _seek(self, pos):
        if self._player:
            self._player.setPosition(pos)

    def _on_pos(self, pos):
        self.slider.blockSignals(True)
        self.slider.setValue(pos)
        self.slider.blockSignals(False)
        self.time.setText(f"{self._fmt(pos)} / {self._fmt(self._player.duration())}")

    def _on_dur(self, dur):
        self.slider.setRange(0, dur)

    def _on_state(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸  Pausar")
        else:
            self.play_btn.setText("▶  Ouvir áudio")

    @staticmethod
    def _fmt(ms):
        s = ms // 1000
        return f"{s // 60:02d}:{s % 60:02d}"

    def stop(self):
        if self._player:
            self._player.stop()
