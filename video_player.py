"""
Player de vídeo embutido com painel de legenda.
Usa QMediaPlayer (PyQt6.QtMultimedia) + QVideoWidget.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QSizePolicy, QTextEdit, QTextBrowser, QSplitter, QFrame,
    QApplication, QStyle
)
from PyQt6.QtCore import Qt, QUrl, QTimer

import json
import html
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

import os


class VideoPlayer(QWidget):
    """Player de vídeo com suporte a legendas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Screvo — Player")
        self.setMinimumSize(900, 550)
        self.resize(1100, 650)
        self.setStyleSheet("background-color: #1a1a1a;")

        self._subtitle_text = ""
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(44)
        header.setStyleSheet("background: #111; border-bottom: 1px solid #333;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        self.title_label = QLabel("Nenhum vídeo")
        self.title_label.setStyleSheet("color: white; font-size: 14px; font-weight: 600;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #888; font-size: 16px; border-radius: 16px; }
            QPushButton:hover { background: rgba(255,255,255,0.1); color: white; }
        """)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)

        main_layout.addWidget(header)

        # Splitter: vídeo | legenda
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setStyleSheet("""
            QSplitter::handle { background: #333; width: 2px; }
        """)

        # === Vídeo ===
        video_container = QWidget()
        video_container.setStyleSheet("background: black;")
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(0)

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background: black;")
        video_layout.addWidget(self.video_widget, 1)

        self.splitter.addWidget(video_container)

        # === Painel de legenda ===
        self.subtitle_panel = QWidget()
        self.subtitle_panel.setMinimumWidth(250)
        self.subtitle_panel.setMaximumWidth(400)
        self.subtitle_panel.setStyleSheet("background: #111;")

        sub_layout = QVBoxLayout(self.subtitle_panel)
        sub_layout.setContentsMargins(12, 12, 12, 12)
        sub_layout.setSpacing(8)

        sub_header = QLabel("📝  Legenda")
        sub_header.setStyleSheet(
            "color: #FF69B4; font-size: 14px; font-weight: 600; padding: 4px 0;"
        )
        sub_layout.addWidget(sub_header)

        self.subtitle_display = QTextBrowser()
        self.subtitle_display.setReadOnly(True)
        self.subtitle_display.setOpenLinks(False)
        self.subtitle_display.setOpenExternalLinks(False)
        self.subtitle_display.anchorClicked.connect(self._on_anchor_clicked)
        self.subtitle_display.setStyleSheet("""
            QTextBrowser {
                background: #1a1a1a; color: #DDD; font-size: 13px;
                border: 1px solid #333; border-radius: 8px; padding: 10px;
                line-height: 1.6;
            }
            a { color: #FF69B4; text-decoration: none; font-weight: 600; }
        """)
        self.subtitle_display.setFont(QFont("Segoe UI", 12))
        sub_layout.addWidget(self.subtitle_display, 1)

        self.splitter.addWidget(self.subtitle_panel)
        self.subtitle_panel.hide()  # Esconde se não tiver legenda

        self.splitter.setSizes([800, 300])
        main_layout.addWidget(self.splitter, 1)

        # === Controles ===
        controls = QWidget()
        controls.setFixedHeight(80)
        controls.setStyleSheet("background: #111;")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(16, 8, 16, 8)
        controls_layout.setSpacing(6)

        # Barra de progresso
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #333; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal {
                background: #FF69B4; border: none; width: 14px; height: 14px;
                margin: -5px 0; border-radius: 7px;
            }
            QSlider::sub-page:horizontal { background: #FF69B4; border-radius: 2px; }
        """)
        self.seek_slider.sliderMoved.connect(self._seek)
        controls_layout.addWidget(self.seek_slider)

        # Botões + tempo
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        # Play/Pause
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet("""
            QPushButton {
                background: #FF69B4; border: none; border-radius: 20px;
                color: white; font-size: 16px;
            }
            QPushButton:hover { background: #FF91A4; }
        """)
        self.play_btn.clicked.connect(self._toggle_play)
        btn_row.addWidget(self.play_btn)

        # Stop
        stop_btn = QPushButton("⏹")
        stop_btn.setFixedSize(36, 36)
        stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        stop_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: 1px solid #444; border-radius: 18px;
                color: #888; font-size: 14px;
            }
            QPushButton:hover { border-color: #FF69B4; color: #FF69B4; }
        """)
        stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(stop_btn)

        # Tempo
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #888; font-size: 12px; font-family: Consolas;")
        btn_row.addWidget(self.time_label)

        btn_row.addStretch()

        # Volume
        vol_icon = QLabel("🔊")
        vol_icon.setStyleSheet("font-size: 14px;")
        btn_row.addWidget(vol_icon)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #333; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal {
                background: white; border: none; width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px;
            }
            QSlider::sub-page:horizontal { background: #666; border-radius: 2px; }
        """)
        self.volume_slider.valueChanged.connect(self._set_volume)
        btn_row.addWidget(self.volume_slider)

        controls_layout.addLayout(btn_row)
        main_layout.addWidget(controls)

        # Media player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)

    def load_video(self, video_path, subtitle_path=None):
        """Carrega vídeo e opcionalmente legenda."""
        self.player.setSource(QUrl.fromLocalFile(video_path))
        self.title_label.setText(os.path.basename(video_path))

        # Carrega legenda — prioriza segmentos com timestamps clicáveis
        seg_path = os.path.splitext(video_path)[0] + ".segments.json"
        loaded = False
        if os.path.isfile(seg_path):
            loaded = self._load_segments(seg_path)

        if not loaded and subtitle_path and os.path.isfile(subtitle_path):
            try:
                with open(subtitle_path, "r", encoding="utf-8") as f:
                    self._subtitle_text = f.read()
                self.subtitle_display.setPlainText(self._subtitle_text)
                self.subtitle_panel.show()
                loaded = True
            except Exception:
                pass

        if not loaded:
            self.subtitle_panel.hide()
            self._subtitle_text = ""

        self.show()
        self.raise_()

    def _load_segments(self, seg_path):
        """Renderiza segmentos com timestamps clicáveis (e falante, se houver)."""
        try:
            with open(seg_path, "r", encoding="utf-8") as f:
                segments = json.load(f)
        except Exception:
            return False
        if not segments:
            return False

        rows = []
        for seg in segments:
            start = float(seg.get("start", 0))
            ts = self._format_time(int(start * 1000))
            speaker = seg.get("speaker")
            spk = (f"<b style='color:#B39DDB'>{html.escape(speaker)}</b> "
                   if speaker else "")
            text = html.escape(seg.get("text", ""))
            rows.append(
                f"<p style='margin:0 0 10px 0;'>"
                f"<a href='seek:{start}'>[{ts}]</a> {spk}"
                f"<span style='color:#DDD'>{text}</span></p>"
            )
        self._subtitle_text = "\n".join(s.get("text", "") for s in segments)
        self.subtitle_display.setHtml("".join(rows))
        self.subtitle_panel.show()
        return True

    def _on_anchor_clicked(self, url):
        s = url.toString()
        if s.startswith("seek:"):
            try:
                seconds = float(s.split(":", 1)[1])
                self.player.setPosition(int(seconds * 1000))
                self.player.play()
            except Exception:
                pass

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _stop(self):
        self.player.stop()

    def _seek(self, position):
        self.player.setPosition(position)

    def _set_volume(self, value):
        self.audio_output.setVolume(value / 100.0)

    def _on_position_changed(self, position):
        self.seek_slider.blockSignals(True)
        self.seek_slider.setValue(position)
        self.seek_slider.blockSignals(False)

        current = self._format_time(position)
        total = self._format_time(self.player.duration())
        self.time_label.setText(f"{current} / {total}")

    def _on_duration_changed(self, duration):
        self.seek_slider.setRange(0, duration)

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸")
        else:
            self.play_btn.setText("▶")

    @staticmethod
    def _format_time(ms):
        s = ms // 1000
        m = s // 60
        s = s % 60
        h = m // 60
        m = m % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)
