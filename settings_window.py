"""
Janela principal de configurações — estilo Handy com sidebar rosa e páginas.
"""

import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QScrollArea, QFrame, QComboBox,
    QSlider, QLineEdit, QFileDialog, QSizePolicy, QSpacerItem,
    QApplication, QGraphicsDropShadowEffect, QInputDialog,
    QMessageBox, QProgressBar, QListView, QSizeGrip, QComboBox as _QComboBox
)
from PyQt6.QtCore import Qt, QSize, QPoint, pyqtSignal
from PyQt6.QtGui import QIcon, QColor, QFont, QPixmap
from styles import MAIN_STYLESHEET
from toggle_switch import ToggleSwitch
from config import Config
from local_transcriber import LocalTranscriber
from video_player import VideoPlayer
from ai_summarizer import SummarizeWorker, DEFAULT_MODELS
from flow_layout import FlowWidget
from text_viewer import TextViewerDialog
from icons import make_icon, make_app_icon
from chat_dialog import ChatDialog
from ocr_screen import OcrWorker
from report_builder import ReportWorker
from audio_player_bar import AudioPlayerBar
import summary_templates
import local_llm
import gpu_info

# Sufixos dos arquivos associados a um vídeo (base = nome sem extensão)
SIDECAR_SUFFIXES = [
    ".txt", "_resumo.txt", ".segments.json", "_tela.txt", ".markers.txt",
    "_relatorio.md", ".mp3",
]
# Subpasta com as imagens do relatório (sufixo de diretório)
REPORT_IMG_SUFFIX = "_relatorio_arquivos"


class TitleBar(QWidget):
    """Barra de título customizada (janela frameless): arrastar + minimizar/fechar."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._win = window
        self._drag_offset = None
        self.setFixedHeight(40)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 10, 6)
        layout.setSpacing(6)
        layout.addStretch()

        btn_qss = (
            "QPushButton {{ background: transparent; border: none; border-radius: 8px; "
            "color: #999; font-size: 15px; min-width: 30px; max-width: 30px; "
            "min-height: 30px; max-height: 30px; }}"
            "QPushButton:hover {{ background: {hover}; color: {fg}; }}"
        )

        self.min_btn = QPushButton("—")
        self.min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.min_btn.setStyleSheet(btn_qss.format(hover="#FFE4E9", fg="#FF69B4"))
        self.min_btn.clicked.connect(self._win.showMinimized)
        layout.addWidget(self.min_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(btn_qss.format(hover="#FFCDD2", fg="#C62828"))
        self.close_btn.clicked.connect(self._win.close)
        layout.addWidget(self.close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self._win.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._win.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    def mouseDoubleClickEvent(self, event):
        # Duplo clique maximiza / restaura
        if self._win.isMaximized():
            self._win.showNormal()
        else:
            self._win.showMaximized()


class SettingRow(QFrame):
    """Uma linha de configuração dentro de um card."""

    def __init__(self, label_text, widget=None, description=None, parent=None):
        super().__init__(parent)
        self.setProperty("class", "settingRow")
        self.setStyleSheet(
            "QFrame { background: transparent; padding: 8px 16px; min-height: 40px; }"
            "QFrame:hover { background-color: #FFF5F7; border-radius: 8px; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Label + description
        label_container = QVBoxLayout()
        label_container.setSpacing(2)

        label = QLabel(label_text)
        label.setStyleSheet("font-size: 13px; font-weight: 500; color: #333;")
        label_container.addWidget(label)

        if description:
            desc = QLabel(description)
            desc.setStyleSheet("font-size: 11px; color: #AAAAAA;")
            desc.setWordWrap(True)
            label_container.addWidget(desc)

        layout.addLayout(label_container, 1)

        # Widget à direita
        if widget:
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignRight)


class SettingCard(QFrame):
    """Card contendo múltiplas linhas de configuração."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "SettingCard { background-color: white; border: 1px solid #F0F0F0; "
            "border-radius: 12px; }"
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 4)
        self._layout.setSpacing(0)
        self._row_count = 0

    def add_row(self, row: SettingRow):
        if self._row_count > 0:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background-color: #F0F0F0; margin: 0px 16px;")
            self._layout.addWidget(sep)
        self._layout.addWidget(row)
        self._row_count += 1


class SectionTitle(QLabel):
    """Título de seção (ex: GERAL, SOM)."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #999; "
            "letter-spacing: 1px; padding: 15px 0px 8px 0px;"
        )


class SettingsWindow(QMainWindow):
    """Janela de configurações do Screvo."""
    hotkey_changed = pyqtSignal(str)
    settings_changed = pyqtSignal()
    _audio_devices_loaded = pyqtSignal(list)
    _gpu_detected = pyqtSignal(dict)

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Screvo")
        self.setWindowIcon(make_app_icon(256))
        self.setMinimumSize(560, 480)
        self.resize(800, 600)
        self.setObjectName("settingsWindow")

        # Janela sem borda nativa + fundo transparente (para cantos arredondados)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Deixa o QMainWindow transparente; os cantos arredondados vêm da
        # sidebar (esquerda) e da área de conteúdo (direita).
        self.setStyleSheet(
            MAIN_STYLESHEET
            + "\n#settingsWindow { background: transparent; }"
            + "\nQMainWindow { background: transparent; }"
        )

        self._audio_devices_loaded.connect(self._populate_audio_combo)
        self._gpu_detected.connect(self._apply_gpu)

        self._setup_ui()
        self._load_settings()
        self._style_combo_popups()

        # Carrega a lista de microfones automaticamente (em background,
        # para não travar a abertura da janela).
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, self._refresh_audio_devices)

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("centralRoot")
        central.setStyleSheet("#centralRoot { background: transparent; }")
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== SIDEBAR =====
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet(
            "#sidebar { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #FFB6C1, stop:0.5 #FF91A4, stop:1 #FF69B4); "
            "border-top-left-radius: 16px; border-bottom-left-radius: 16px; }"
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Logo
        logo = QLabel("Screvo")
        logo.setObjectName("appLogo")
        logo.setStyleSheet(
            "font-size: 30px; font-weight: 800; color: white; letter-spacing: 1px; "
            "padding: 30px 20px 4px 20px; font-family: 'Segoe UI Black';"
        )
        sidebar_layout.addWidget(logo)

        tagline = QLabel("grava e transcreve")
        tagline.setStyleSheet(
            "color: rgba(255,255,255,0.75); font-size: 11px; "
            "padding: 0px 20px 10px 20px; font-style: italic;"
        )
        sidebar_layout.addWidget(tagline)

        # Ícone/ilustração do app (icon.png), logo abaixo do título
        icon_path = self._find_asset("icon.png")
        if icon_path:
            pm = QPixmap(icon_path)
            if not pm.isNull():
                icon_img = QLabel()
                icon_img.setPixmap(
                    pm.scaledToWidth(150, Qt.TransformationMode.SmoothTransformation)
                )
                icon_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_img.setStyleSheet("background: transparent; padding: 2px 10px 16px 10px;")
                sidebar_layout.addWidget(icon_img)

        # Botões da sidebar
        self.sidebar_buttons = []
        pages = [
            ("Geral", "geral", 0),
            ("Áudio", "audio", 1),
            ("Avançado", "avancado", 2),
            ("Transcrição", "transcricao", 3),
            ("IA", "ia", 4),
            ("Vídeos", "videos", 5),
            ("Sobre", "sobre", 6),
        ]

        for text, icon_name, index in pages:
            btn = QPushButton("   " + text)
            btn.setIcon(make_icon(icon_name, 22))
            btn.setIconSize(QSize(22, 22))
            btn.setProperty("class", "sidebarBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; "
                "color: rgba(255,255,255,0.85); text-align: left; padding: 12px 20px; "
                "font-size: 14px; font-weight: 500; border-radius: 8px; margin: 2px 10px; }"
                "QPushButton:hover { background: rgba(255,255,255,0.2); color: white; }"
            )
            btn.clicked.connect(lambda checked, i=index: self._switch_page(i))
            sidebar_layout.addWidget(btn)
            self.sidebar_buttons.append(btn)

        sidebar_layout.addStretch()

        # Versão
        version_label = QLabel("v1.0.0")
        version_label.setStyleSheet(
            "color: rgba(255,255,255,0.5); font-size: 11px; padding: 10px 20px;"
        )
        sidebar_layout.addWidget(version_label)

        main_layout.addWidget(sidebar)

        # ===== CONTENT AREA =====
        content = QWidget()
        content.setObjectName("contentArea")
        content.setStyleSheet(
            "#contentArea { background-color: #FAFAFA; "
            "border-top-right-radius: 16px; border-bottom-right-radius: 16px; }"
        )
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Barra de título customizada (janela frameless)
        self.title_bar = TitleBar(self)
        content_layout.addWidget(self.title_bar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("contentStack")
        content_layout.addWidget(self.stack, 1)

        # Alça de redimensionamento no canto inferior direito
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 4, 4)
        grip_row.addStretch()
        size_grip = QSizeGrip(content)
        size_grip.setStyleSheet("background: transparent;")
        grip_row.addWidget(size_grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        content_layout.addLayout(grip_row)

        # Páginas
        self.stack.addWidget(self._create_general_page())
        self.stack.addWidget(self._create_audio_page())
        self.stack.addWidget(self._create_advanced_page())
        self.stack.addWidget(self._create_speech_page())
        self.stack.addWidget(self._create_ia_page())
        self.stack.addWidget(self._create_videos_page())
        self.stack.addWidget(self._create_about_page())

        # Player e transcriber
        self.video_player = VideoPlayer()

        # Transcritor local (offline) — Parakeet V3
        self.local_transcriber = LocalTranscriber(config=self.config)
        self.local_transcriber.progress.connect(self._on_transcribe_progress)
        self.local_transcriber.finished.connect(self._on_transcribe_finished)
        self.local_transcriber.error.connect(self._on_transcribe_error)
        self.local_transcriber.status.connect(self._on_transcribe_status)

        main_layout.addWidget(content, 1)

        # Seleciona primeira página
        self._switch_page(0)

    def _switch_page(self, index):
        self.stack.setCurrentIndex(index)

        # Ao abrir a aba Vídeos (5), recarrega a lista automaticamente.
        # Ao abrir Speech (3), atualiza o status do modelo Parakeet.
        if index == 5 and hasattr(self, "videos_container"):
            self._refresh_videos_list()
        elif index == 3 and hasattr(self, "parakeet_status"):
            self._update_parakeet_status()

        for i, btn in enumerate(self.sidebar_buttons):
            if i == index:
                btn.setStyleSheet(
                    "QPushButton { background: rgba(255,255,255,0.35); border: none; "
                    "color: white; text-align: left; padding: 12px 20px; "
                    "font-size: 14px; font-weight: 600; border-radius: 8px; margin: 2px 10px; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background: transparent; border: none; "
                    "color: rgba(255,255,255,0.85); text-align: left; padding: 12px 20px; "
                    "font-size: 14px; font-weight: 500; border-radius: 8px; margin: 2px 10px; }"
                    "QPushButton:hover { background: rgba(255,255,255,0.2); color: white; }"
                )

    def _find_asset(self, name):
        """Procura um arquivo de recurso (ex.: icon.png) em vários locais."""
        import os
        import sys
        candidates = []
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", "")
            if meipass:
                candidates.append(os.path.join(meipass, name))
                candidates.append(os.path.join(meipass, "resources", name))
        try:
            from config import get_app_dir
            base = get_app_dir()
            candidates += [
                os.path.join(base, name),
                os.path.join(base, "resources", name),
            ]
        except Exception:
            pass
        for c in candidates:
            if c and os.path.isfile(c):
                return c
        return None

    def _make_scroll_page(self):
        """Cria scroll area para uma página."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Remove a barra de rolagem horizontal (a "barra deslizante" indesejada)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 20, 30, 30)
        layout.setSpacing(12)

        scroll.setWidget(container)
        return scroll, layout

    # =================== GERAL ===================
    def _create_general_page(self):
        scroll, layout = self._make_scroll_page()

        # GERAL
        layout.addWidget(SectionTitle("GERAL"))

        card = SettingCard()

        # Atalho de Gravação
        self.hotkey_btn = QPushButton(self.config.get("hotkey", "ctrl+shift+r").replace("+", " + ").title())
        self.hotkey_btn.setStyleSheet(
            "QPushButton { background-color: #F5F5F5; border: 1px solid #E8E8E8; "
            "border-radius: 8px; padding: 8px 16px; font-weight: 500; min-width: 140px; }"
            "QPushButton:hover { border-color: #FFB6C1; }"
        )
        self.hotkey_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hotkey_btn.clicked.connect(self._capture_hotkey)

        hotkey_layout = QHBoxLayout()
        hotkey_layout.setSpacing(8)
        hotkey_layout.addWidget(self.hotkey_btn)

        reset_hotkey = QPushButton("↻")
        reset_hotkey.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #E8E8E8; "
            "border-radius: 6px; padding: 6px; min-width: 28px; max-width: 28px; "
            "min-height: 28px; max-height: 28px; font-size: 14px; }"
            "QPushButton:hover { background: #FFE4E9; }"
        )
        reset_hotkey.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_hotkey.clicked.connect(lambda: self._set_hotkey("ctrl+shift+r"))
        hotkey_layout.addWidget(reset_hotkey)

        hotkey_widget = QWidget()
        hotkey_widget.setLayout(hotkey_layout)

        card.add_row(SettingRow("Atalho de Gravação", hotkey_widget,
                                "Pressione para alterar o atalho"))

        layout.addWidget(card)

        # PASTA DE SAÍDA
        layout.addWidget(SectionTitle("SAÍDA"))

        card2 = SettingCard()

        # Pasta
        folder_layout = QHBoxLayout()
        folder_layout.setSpacing(8)

        self.folder_input = QLineEdit(self.config.get("output_folder"))
        self.folder_input.setStyleSheet(
            "QLineEdit { background-color: #F5F5F5; border: 1px solid #E8E8E8; "
            "border-radius: 8px; padding: 8px 12px; font-size: 12px; min-width: 250px; }"
            "QLineEdit:focus { border-color: #FF69B4; background: white; }"
        )
        self.folder_input.setReadOnly(True)
        folder_layout.addWidget(self.folder_input)

        browse_btn = QPushButton("Procurar")
        browse_btn.setStyleSheet(
            "QPushButton { background-color: #FF69B4; border: none; border-radius: 8px; "
            "padding: 8px 20px; color: white; font-weight: 600; }"
            "QPushButton:hover { background-color: #FF91A4; }"
        )
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(browse_btn)

        folder_widget = QWidget()
        folder_widget.setLayout(folder_layout)

        card2.add_row(SettingRow("Pasta de Gravação", folder_widget))

        # Formato
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "mkv", "avi", "webm"])
        self.format_combo.setCurrentText(self.config.get("format", "mp4"))
        self.format_combo.currentTextChanged.connect(
            lambda v: self._save_setting("format", v)
        )
        card2.add_row(SettingRow("Formato de Saída", self.format_combo))

        layout.addWidget(card2)

        layout.addStretch()
        return scroll

    # =================== ÁUDIO ===================
    def _create_audio_page(self):
        scroll, layout = self._make_scroll_page()

        layout.addWidget(SectionTitle("SOM"))

        card = SettingCard()

        # Modo de áudio
        self.audio_mode_combo = QComboBox()
        self.audio_mode_combo.addItem("Sistema + Microfone", "system_mic")
        self.audio_mode_combo.addItem("Só o microfone", "mic")
        self.audio_mode_combo.addItem("Só o áudio do sistema", "system")
        self.audio_mode_combo.addItem("Todos os microfones", "all")
        self.audio_mode_combo.setMinimumWidth(250)
        _mi = self.audio_mode_combo.findData(self.config.get("audio_mode", "system_mic"))
        self.audio_mode_combo.setCurrentIndex(_mi if _mi >= 0 else 0)
        self.audio_mode_combo.currentIndexChanged.connect(self._on_audio_mode_changed)
        card.add_row(SettingRow(
            "Modo de Áudio", self.audio_mode_combo,
            "\"Sistema\" precisa de um dispositivo de loopback (Mixagem Estéreo ou cabo virtual)"
        ))

        # Microfone (usado nos modos Sistema+Microfone e Só microfone)
        self.audio_combo = QComboBox()
        self.audio_combo.addItem("Automático (primeiro microfone)", "auto")
        # Dispositivos reais são populados automaticamente ao abrir (abaixo)
        self.audio_combo.setMinimumWidth(250)
        self.audio_combo.currentIndexChanged.connect(self._on_audio_device_changed)

        audio_layout = QHBoxLayout()
        audio_layout.setSpacing(8)
        audio_layout.addWidget(self.audio_combo)

        refresh_audio = QPushButton("↻")
        refresh_audio.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #E8E8E8; "
            "border-radius: 6px; padding: 6px; min-width: 28px; max-width: 28px; "
            "min-height: 28px; max-height: 28px; font-size: 14px; }"
            "QPushButton:hover { background: #FFE4E9; }"
        )
        refresh_audio.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_audio.clicked.connect(self._refresh_audio_devices)
        audio_layout.addWidget(refresh_audio)

        audio_widget = QWidget()
        audio_widget.setLayout(audio_layout)

        card.add_row(SettingRow("Microfone", audio_widget))

        # Silenciar durante gravação
        self.mute_toggle = ToggleSwitch(checked=self.config.get("mute_during_recording", False))
        self.mute_toggle.toggled.connect(
            lambda v: self._save_setting("mute_during_recording", v)
        )
        card.add_row(SettingRow("Silenciar Durante Gravação", self.mute_toggle,
                                "Silencia o áudio do sistema durante a gravação"))

        # Áudio habilitado
        self.audio_toggle = ToggleSwitch(checked=self.config.get("audio_enabled", True))
        self.audio_toggle.toggled.connect(
            lambda v: self._save_setting("audio_enabled", v)
        )
        card.add_row(SettingRow("Gravar Áudio", self.audio_toggle,
                                "Captura o áudio do sistema junto com o vídeo"))

        layout.addWidget(card)

        # Indicador de status do "som do sistema" (loopback)
        self.loopback_status = QLabel("")
        self.loopback_status.setWordWrap(True)
        self.loopback_status.setStyleSheet(
            "color: #999; font-size: 12px; padding: 10px; "
            "background: #FFF5F7; border-radius: 8px; border: 1px solid #FFE4E9;"
        )
        layout.addWidget(self.loopback_status)

        # Volume
        layout.addWidget(SectionTitle("VOLUME"))

        card2 = SettingCard()

        vol_layout = QHBoxLayout()
        vol_layout.setSpacing(12)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.config.get("volume", 100))
        self.volume_slider.setMinimumWidth(200)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        vol_layout.addWidget(self.volume_slider)

        self.volume_label = QLabel(f"{self.config.get('volume', 100)}%")
        self.volume_label.setStyleSheet("font-weight: 600; color: #FF69B4; min-width: 40px;")
        vol_layout.addWidget(self.volume_label)

        vol_widget = QWidget()
        vol_widget.setLayout(vol_layout)

        card2.add_row(SettingRow("Volume", vol_widget))
        layout.addWidget(card2)

        layout.addStretch()
        return scroll

    # =================== AVANÇADO ===================
    def _create_advanced_page(self):
        scroll, layout = self._make_scroll_page()

        layout.addWidget(SectionTitle("APLICATIVO"))

        card = SettingCard()

        # Iniciar oculto
        self.hidden_toggle = ToggleSwitch(checked=self.config.get("start_hidden", False))
        self.hidden_toggle.toggled.connect(
            lambda v: self._save_setting("start_hidden", v)
        )
        card.add_row(SettingRow("Iniciar Oculto", self.hidden_toggle,
                                "Inicia minimizado na bandeja do sistema"))

        # Iniciar com Windows
        self.startup_toggle = ToggleSwitch(checked=self.config.get("start_with_windows", False))
        self.startup_toggle.toggled.connect(self._on_startup_changed)
        card.add_row(SettingRow("Iniciar na Inicialização", self.startup_toggle,
                                "Inicia automaticamente com o Windows"))

        # Ícone na bandeja
        self.tray_toggle = ToggleSwitch(checked=self.config.get("show_tray_icon", True))
        self.tray_toggle.toggled.connect(
            lambda v: self._save_setting("show_tray_icon", v)
        )
        card.add_row(SettingRow("Mostrar Ícone na Bandeja", self.tray_toggle))

        layout.addWidget(card)

        # GRAVAÇÃO
        layout.addWidget(SectionTitle("GRAVAÇÃO"))

        card2 = SettingCard()

        # FPS
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["15", "24", "30", "60"])
        self.fps_combo.setCurrentText(str(self.config.get("fps", 30)))
        self.fps_combo.currentTextChanged.connect(
            lambda v: self._save_setting("fps", int(v))
        )
        card2.add_row(SettingRow("FPS (Quadros por Segundo)", self.fps_combo))

        # Qualidade
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["low", "medium", "high", "ultra"])
        self.quality_combo.setCurrentText(self.config.get("quality", "high"))
        self.quality_combo.currentTextChanged.connect(
            lambda v: self._save_setting("quality", v)
        )
        card2.add_row(SettingRow("Qualidade", self.quality_combo))

        # Codec
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["h264", "h265"])
        self.codec_combo.setCurrentText(self.config.get("codec", "h264"))
        self.codec_combo.currentTextChanged.connect(
            lambda v: self._save_setting("codec", v)
        )
        card2.add_row(SettingRow("Codec de Vídeo", self.codec_combo))

        # Posição do overlay
        self.overlay_combo = QComboBox()
        self.overlay_combo.addItem("Inferior", "bottom")
        self.overlay_combo.addItem("Superior", "top")
        idx = 0 if self.config.get("overlay_position", "bottom") == "bottom" else 1
        self.overlay_combo.setCurrentIndex(idx)
        self.overlay_combo.currentIndexChanged.connect(
            lambda i: self._save_setting("overlay_position", self.overlay_combo.itemData(i))
        )
        card2.add_row(SettingRow("Posição da Sobreposição", self.overlay_combo,
                                 "Posição do overlay durante gravação"))

        layout.addWidget(card2)

        layout.addStretch()
        return scroll

    # =================== SPEECH ===================
    def _create_speech_page(self):
        scroll, layout = self._make_scroll_page()

        layout.addWidget(SectionTitle("TRANSCRIÇÃO (LOCAL)"))

        card = SettingCard()

        # Modelo (fixo: Parakeet V3) + botão de baixar
        self.parakeet_dl_btn = QPushButton("Baixar modelo")
        self.parakeet_dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.parakeet_dl_btn.setStyleSheet(
            "QPushButton { background-color: #FF69B4; border: none; border-radius: 8px; "
            "padding: 8px 18px; color: white; font-weight: 600; }"
            "QPushButton:hover { background-color: #FF91A4; }"
        )
        self.parakeet_dl_btn.clicked.connect(self._download_parakeet)
        card.add_row(SettingRow(
            "Parakeet V3", self.parakeet_dl_btn,
            "Modelo NVIDIA Parakeet TDT v3 — rápido, multilíngue, ~600 MB"
        ))

        layout.addWidget(card)

        # Status do modelo
        self.parakeet_status = QLabel("")
        self.parakeet_status.setWordWrap(True)
        self.parakeet_status.setStyleSheet(
            "color: #666; font-size: 12px; padding: 10px; "
            "background: #FFF5F7; border-radius: 8px; border: 1px solid #FFE4E9;"
        )
        layout.addWidget(self.parakeet_status)
        self._update_parakeet_status()

        note = QLabel(
            "A transcrição roda 100% na sua máquina (offline), sem enviar o áudio "
            "para nenhum servidor. O modelo é baixado uma única vez e fica em cache. "
            "Depois, é só usar o botão \"Criar Legenda\" na aba Vídeos."
        )
        note.setStyleSheet(
            "color: #999; font-size: 12px; padding: 20px; "
            "background: #FFF5F7; border-radius: 10px; border: 1px solid #FFE4E9;"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()
        return scroll

    def _update_parakeet_status(self):
        """Atualiza o texto de status do modelo Parakeet."""
        if not hasattr(self, "parakeet_status"):
            return
        if LocalTranscriber.model_downloaded():
            self.parakeet_status.setText("✅ Modelo Parakeet V3 baixado e pronto para uso.")
            self.parakeet_status.setStyleSheet(
                "color: #2E7D32; font-size: 12px; padding: 10px; "
                "background: #E8F5E9; border-radius: 8px; border: 1px solid #A5D6A7;"
            )
            self.parakeet_dl_btn.setText("Baixar novamente")
        else:
            self.parakeet_status.setText(
                "⏳ Modelo ainda não baixado. Ele é baixado automaticamente na primeira "
                "transcrição, ou clique em \"Baixar modelo\" para adiantar (precisa de internet)."
            )
            self.parakeet_status.setStyleSheet(
                "color: #E65100; font-size: 12px; padding: 10px; "
                "background: #FFF3E0; border-radius: 8px; border: 1px solid #FFCC80;"
            )

    def _download_parakeet(self):
        """Baixa o modelo Parakeet em segundo plano."""
        self.parakeet_dl_btn.setEnabled(False)
        self.transcribe_status.show()
        self.transcribe_progress.show()
        self.transcribe_status.setText("Preparando download...")
        self.transcribe_progress.setValue(0)
        self.local_transcriber.download_model()

    # =================== IA ===================
    def _create_ia_page(self):
        scroll, layout = self._make_scroll_page()

        layout.addWidget(SectionTitle("PROVEDOR DE IA"))

        card = SettingCard()

        # Provedor
        self.ia_provider_combo = QComboBox()
        self.ia_provider_combo.setMinimumWidth(220)
        self.ia_provider_combo.addItem("— Selecione —", "")
        self.ia_provider_combo.addItem("IA local no app — Gemma", "local")
        self.ia_provider_combo.addItem("Google Gemini", "gemini")
        self.ia_provider_combo.addItem("Claude (Anthropic)", "claude")
        self.ia_provider_combo.addItem("OpenAI", "openai")
        self.ia_provider_combo.addItem("DeepSeek", "deepseek")
        _pi = self.ia_provider_combo.findData(self.config.get("ia_provider", ""))
        self.ia_provider_combo.setCurrentIndex(_pi if _pi >= 0 else 0)
        self.ia_provider_combo.currentIndexChanged.connect(self._on_ia_provider_changed)
        card.add_row(SettingRow(
            "Provedor", self.ia_provider_combo,
            "Serviço usado para gerar o resumo das legendas"
        ))

        # Modelo
        self.ia_model_input = QLineEdit(self.config.get("ia_model", ""))
        self.ia_model_input.setMinimumWidth(220)
        self.ia_model_input.setStyleSheet(
            "QLineEdit { background-color: #F5F5F5; border: 1px solid #E8E8E8; "
            "border-radius: 8px; padding: 8px 12px; font-size: 12px; }"
            "QLineEdit:focus { border-color: #FF69B4; background: white; }"
        )
        self._update_ia_model_placeholder()
        self.ia_model_input.textChanged.connect(
            lambda v: self._save_setting("ia_model", v.strip())
        )
        card.add_row(SettingRow(
            "Modelo", self.ia_model_input,
            "Nome do modelo. Deixe em branco para usar o padrão do provedor."
        ))

        # API Key
        self.ia_key_input = QLineEdit(self.config.get("ia_api_key", ""))
        self.ia_key_input.setMinimumWidth(220)
        self.ia_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ia_key_input.setStyleSheet(
            "QLineEdit { background-color: #F5F5F5; border: 1px solid #E8E8E8; "
            "border-radius: 8px; padding: 8px 12px; font-size: 12px; }"
            "QLineEdit:focus { border-color: #FF69B4; background: white; }"
        )
        self.ia_key_input.setPlaceholderText("Cole aqui a sua API key")
        self.ia_key_input.textChanged.connect(
            lambda v: self._save_setting("ia_api_key", v.strip())
        )
        card.add_row(SettingRow(
            "API Key", self.ia_key_input,
            "Sua chave fica salva apenas neste computador."
        ))

        # Template de resumo
        self.ia_template_combo = QComboBox()
        self.ia_template_combo.setMinimumWidth(220)
        for key, label in summary_templates.labels():
            self.ia_template_combo.addItem(label, key)
        _ti = self.ia_template_combo.findData(self.config.get("ia_template", "geral"))
        self.ia_template_combo.setCurrentIndex(_ti if _ti >= 0 else 0)
        self.ia_template_combo.currentIndexChanged.connect(
            lambda i: self._save_setting("ia_template", self.ia_template_combo.itemData(i))
        )
        card.add_row(SettingRow(
            "Template de Resumo", self.ia_template_combo,
            "Formato do resumo gerado (ata, tutorial, tarefas, etc.)"
        ))

        layout.addWidget(card)

        # ---------- IA LOCAL (NO APP · GEMMA) ----------
        layout.addWidget(SectionTitle("IA LOCAL NO APP · GEMMA"))
        local_card = SettingCard()

        # Hardware detectado
        self.gpu_label = QLabel("Detectando hardware...")
        self.gpu_label.setStyleSheet("font-size: 12px; color: #666;")
        self.gpu_label.setWordWrap(True)
        local_card.add_row(SettingRow("Seu computador", self.gpu_label))

        # Modelo Gemma (local)
        self.local_model_combo = QComboBox()
        self.local_model_combo.setMinimumWidth(240)
        for m in local_llm.LLM_MODELS:
            self.local_model_combo.addItem(m["label"], m["key"])
        _cm = self.local_model_combo.findData(self.config.get("ia_model", ""))
        if _cm >= 0:
            self.local_model_combo.setCurrentIndex(_cm)
        self.local_model_combo.currentIndexChanged.connect(self._on_local_model_changed)
        local_card.add_row(SettingRow(
            "Modelo (Gemma)", self.local_model_combo,
            "Roda por CPU no próprio app. Modelos maiores pedem mais RAM."
        ))

        # Botão baixar/usar
        self.local_dl_btn = QPushButton("Baixar / Usar modelo")
        self.local_dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.local_dl_btn.setStyleSheet(
            "QPushButton { background-color: #FF69B4; border: none; border-radius: 8px; "
            "padding: 8px 18px; color: white; font-weight: 600; }"
            "QPushButton:hover { background-color: #FF91A4; }"
        )
        self.local_dl_btn.clicked.connect(self._download_local_model)
        local_card.add_row(SettingRow("Modelo local", self.local_dl_btn))

        layout.addWidget(local_card)

        # Status + progresso do download local
        self.local_status = QLabel("")
        self.local_status.setWordWrap(True)
        self.local_status.setStyleSheet(
            "color: #666; font-size: 12px; padding: 8px; "
            "background: #FFF5F7; border-radius: 8px; border: 1px solid #FFE4E9;"
        )
        self.local_status.hide()
        layout.addWidget(self.local_status)

        self.local_progress = QProgressBar()
        self.local_progress.setStyleSheet("""
            QProgressBar { background: #F0F0F0; border: none; border-radius: 6px; height: 8px; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #FF69B4, stop:1 #FF91A4); border-radius: 6px; }
        """)
        self.local_progress.setFixedHeight(8)
        self.local_progress.setTextVisible(False)
        self.local_progress.hide()
        layout.addWidget(self.local_progress)

        local_note = QLabel(
            "A IA local roda <b>100% dentro do Screvo</b>, sem programas externos "
            "e sem custo de API. Escolha o modelo Gemma conforme a sua RAM e clique "
            "em \"Baixar / Usar modelo\" — o modelo é baixado uma vez e fica salvo. "
            "A geração é por CPU; modelos maiores são mais lentos."
        )
        local_note.setStyleSheet(
            "color: #999; font-size: 12px; padding: 14px; "
            "background: #F3E5F5; border-radius: 10px; border: 1px solid #E1BEE7;"
        )
        local_note.setWordWrap(True)
        local_note.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(local_note)

        note = QLabel(
            "Para provedores pagos: configure provedor, modelo e API key. Depois, na "
            "aba Vídeos, use \"Resumir IA\", \"Chat\" ou \"Relatório Completo\"."
        )
        note.setStyleSheet(
            "color: #999; font-size: 12px; padding: 20px; "
            "background: #FFF5F7; border-radius: 10px; border: 1px solid #FFE4E9;"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        # Detecta a GPU em segundo plano e ajusta os modelos
        self._gpu = {"name": None, "vram_gb": None}
        self._start_gpu_detection()

        layout.addStretch()
        return scroll

    def _update_ia_model_placeholder(self):
        provider = self.ia_provider_combo.currentData()
        default = DEFAULT_MODELS.get(provider, "")
        self.ia_model_input.setPlaceholderText(f"Padrão: {default}" if default else "")

    def _on_ia_provider_changed(self, index):
        provider = self.ia_provider_combo.itemData(index)
        if provider is not None:
            self._save_setting("ia_provider", provider)
        self._update_ia_model_placeholder()
        # API key não se aplica à IA local
        if hasattr(self, "ia_key_input"):
            self.ia_key_input.setEnabled(provider != "local")

    # ---- IA local (no app) ----
    def _start_gpu_detection(self):
        import threading

        def worker():
            info = {"gpu": {"name": None, "vram_gb": None}, "ram_gb": None}
            try:
                info["gpu"] = gpu_info.detect_gpu()
            except Exception:
                pass
            try:
                info["ram_gb"] = gpu_info.system_ram_gb()
            except Exception:
                pass
            self._gpu_detected.emit(info)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_gpu(self, info):
        self._gpu = info
        gpu = info.get("gpu") or {}
        ram = info.get("ram_gb")
        name = gpu.get("name")
        vram = gpu.get("vram_gb")

        parts = []
        if name and vram:
            parts.append(f"GPU: {name} ({vram:.0f} GB)")
        elif name:
            parts.append(f"GPU: {name}")
        else:
            parts.append("GPU: não detectada")
        if ram:
            parts.append(f"RAM: {ram:.0f} GB")
        self.gpu_label.setText("  •  ".join(parts))

        self._gate_local_models(ram)

    def _gate_local_models(self, ram_gb):
        """Habilita/desabilita modelos conforme a RAM e marca o recomendado."""
        rec = local_llm.recommend(ram_gb)
        model = self.local_model_combo.model()
        for i, m in enumerate(local_llm.LLM_MODELS):
            enabled = local_llm.model_enabled(ram_gb, m)
            item = model.item(i)
            if item is not None:
                item.setEnabled(enabled)
            label = m["label"] + f"  ·  {m['note']}"
            if m["key"] == rec:
                label += "   ⭐ recomendado"
            self.local_model_combo.setItemText(i, label)

        # Seleciona o recomendado SEM trocar o provedor (bloqueia sinais)
        saved = self.config.get("ia_model", "")
        idx = self.local_model_combo.findData(saved)
        need_default = idx < 0 or (
            model.item(idx) is not None and not model.item(idx).isEnabled()
        )
        if need_default:
            ridx = self.local_model_combo.findData(rec)
            if ridx >= 0:
                self.local_model_combo.blockSignals(True)
                self.local_model_combo.setCurrentIndex(ridx)
                self.local_model_combo.blockSignals(False)

    def _on_local_model_changed(self, index):
        key = self.local_model_combo.itemData(index)
        item = self.local_model_combo.model().item(index)
        if item is not None and not item.isEnabled():
            return
        if key:
            self._save_setting("ia_provider", "local")
            self._save_setting("ia_model", key)
            pidx = self.ia_provider_combo.findData("local")
            if pidx >= 0:
                self.ia_provider_combo.setCurrentIndex(pidx)

    def _download_local_model(self):
        key = self.local_model_combo.currentData()
        item = self.local_model_combo.model().item(self.local_model_combo.currentIndex())
        if item is not None and not item.isEnabled():
            QMessageBox.warning(
                self, "Modelo pesado demais",
                "Este modelo pede mais RAM do que o seu computador tem. "
                "Escolha um modelo mais leve."
            )
            return

        if local_llm.is_downloaded(key):
            self._save_setting("ia_provider", "local")
            self._save_setting("ia_model", key)
            pidx = self.ia_provider_combo.findData("local")
            if pidx >= 0:
                self.ia_provider_combo.setCurrentIndex(pidx)
            self.local_status.show()
            self.local_status.setText("✅ Modelo já baixado e pronto (IA local ativa).")
            self.local_status.setStyleSheet(
                "color: #2E7D32; font-size: 12px; padding: 8px; "
                "background: #E8F5E9; border-radius: 8px; border: 1px solid #A5D6A7;"
            )
            return

        # Define como provedor/modelo ativo e baixa
        self._save_setting("ia_provider", "local")
        self._save_setting("ia_model", key)
        pidx = self.ia_provider_combo.findData("local")
        if pidx >= 0:
            self.ia_provider_combo.setCurrentIndex(pidx)

        self.local_dl_btn.setEnabled(False)
        self.local_status.show()
        self.local_status.setStyleSheet(
            "color: #666; font-size: 12px; padding: 8px; "
            "background: #FFF5F7; border-radius: 8px; border: 1px solid #FFE4E9;"
        )
        self.local_progress.show()
        self.local_progress.setRange(0, 0)
        self.local_status.setText("Iniciando download...")

        self._local_worker = local_llm.GgufDownloadWorker(key)
        self._local_worker.progress.connect(self._on_local_progress)
        self._local_worker.status.connect(lambda m: self.local_status.setText(m))
        self._local_worker.finished_ok.connect(self._on_local_dl_done)
        self._local_worker.failed.connect(self._on_local_dl_error)
        self._local_worker.start()

    def _on_local_progress(self, current, total):
        self.local_progress.setRange(0, total)
        self.local_progress.setValue(current)

    def _on_local_dl_done(self, key):
        self.local_progress.setRange(0, 100)
        self.local_progress.setValue(100)
        self.local_progress.hide()
        self.local_dl_btn.setEnabled(True)
        self.local_status.setText("✅ Modelo pronto! A IA local está ativa (sem API).")
        self.local_status.setStyleSheet(
            "color: #2E7D32; font-size: 12px; padding: 8px; "
            "background: #E8F5E9; border-radius: 8px; border: 1px solid #A5D6A7;"
        )

    def _on_local_dl_error(self, msg):
        self.local_progress.hide()
        self.local_dl_btn.setEnabled(True)
        self.local_status.setText(f"Erro ao baixar: {msg}")
        self.local_status.setStyleSheet(
            "color: #D32F2F; font-size: 12px; padding: 8px; "
            "background: #FFEBEE; border-radius: 8px; border: 1px solid #EF9A9A;"
        )

    # =================== VÍDEOS ===================
    def _create_videos_page(self):
        scroll, layout = self._make_scroll_page()

        layout.addWidget(SectionTitle("VÍDEOS"))

        # Botões de ação no TOPO
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        refresh_btn = QPushButton("↻  Atualizar Lista")
        refresh_btn.setStyleSheet(
            "QPushButton { background: #F5F5F5; border: 1px solid #E8E8E8; border-radius: 10px; "
            "padding: 10px 20px; font-size: 13px; font-weight: 500; }"
            "QPushButton:hover { background: #FFE4E9; border-color: #FFB6C1; }"
        )
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh_videos_list)
        btn_row.addWidget(refresh_btn)

        open_folder_btn = QPushButton("📂  Abrir Pasta")
        open_folder_btn.setStyleSheet(
            "QPushButton { background: #FF69B4; border: none; border-radius: 10px; "
            "padding: 10px 20px; color: white; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background: #FF91A4; }"
        )
        open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_folder_btn.clicked.connect(self._open_output_folder)
        btn_row.addWidget(open_folder_btn)

        new_folder_btn = QPushButton("📁  Nova Pasta")
        new_folder_btn.setStyleSheet(
            "QPushButton { background: #F5F5F5; border: 1px solid #E8E8E8; border-radius: 10px; "
            "padding: 10px 20px; font-size: 13px; font-weight: 500; }"
            "QPushButton:hover { background: #FFE4E9; border-color: #FFB6C1; }"
        )
        new_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_folder_btn.clicked.connect(self._create_group_folder)
        btn_row.addWidget(new_folder_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Barra de status da transcrição / resumo
        self.transcribe_status = QLabel("")
        self.transcribe_status.setStyleSheet("color: #FF69B4; font-size: 12px;")
        self.transcribe_status.hide()
        layout.addWidget(self.transcribe_status)

        self.transcribe_progress = QProgressBar()
        self.transcribe_progress.setStyleSheet("""
            QProgressBar {
                background: #F0F0F0; border: none; border-radius: 6px;
                height: 8px; text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF69B4, stop:1 #FF91A4);
                border-radius: 6px;
            }
        """)
        self.transcribe_progress.setFixedHeight(8)
        self.transcribe_progress.setTextVisible(False)
        self.transcribe_progress.hide()
        layout.addWidget(self.transcribe_progress)

        # Container para lista de vídeos (será repopulado)
        self.videos_container = QVBoxLayout()
        self.videos_container.setSpacing(0)
        layout.addLayout(self.videos_container)

        # Popula lista
        self._refresh_videos_list()

        layout.addStretch()
        return scroll

    def _clear_videos_container(self):
        while self.videos_container.count():
            item = self.videos_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _clear_layout(self, lay):
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _list_groups(self):
        """Lista as pastas (grupos) dentro da pasta de saída."""
        import os
        root = self.config.get("output_folder")
        if not os.path.isdir(root):
            return []
        return sorted(
            d for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d))
        )

    def _current_folder(self):
        """Pasta atualmente exibida (raiz ou grupo selecionado)."""
        import os
        root = self.config.get("output_folder")
        group = getattr(self, "_current_group", None)
        if group:
            return os.path.join(root, group)
        return root

    def _make_list_row(self, title, desc, flow_widget, extra_widget=None):
        """Linha de lista responsiva: título + descrição em cima, botões
        (FlowWidget) embaixo, quebrando de linha em janelas estreitas.

        extra_widget (opcional) é adicionado abaixo dos botões (ex.: player).
        """
        row = QFrame()
        row.setStyleSheet(
            "QFrame { background: transparent; padding: 10px 16px; }"
            "QFrame:hover { background-color: #FFF5F7; border-radius: 8px; }"
        )
        v = QVBoxLayout(row)
        v.setContentsMargins(0, 4, 0, 4)
        v.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 500; color: #333;")
        title_lbl.setWordWrap(True)
        v.addWidget(title_lbl)

        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("font-size: 11px; color: #AAAAAA;")
            desc_lbl.setWordWrap(True)
            v.addWidget(desc_lbl)

        v.addWidget(flow_widget)
        if extra_widget is not None:
            v.addWidget(extra_widget)
        return row

    def _refresh_videos_list(self):
        """Atualiza lista de vídeos na aba."""
        self._clear_videos_container()

        import os
        root = self.config.get("output_folder")
        if not os.path.isdir(root):
            no_folder = QLabel("Pasta de saída não encontrada.")
            no_folder.setStyleSheet("color: #999; font-size: 13px; padding: 20px;")
            no_folder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.videos_container.addWidget(no_folder)
            return

        group = getattr(self, "_current_group", None)
        # Se o grupo salvo não existe mais, volta para a raiz
        if group and not os.path.isdir(os.path.join(root, group)):
            self._current_group = None
            group = None
        folder = self._current_folder()

        # Breadcrumb / botão voltar quando dentro de um grupo
        if group:
            crumb_widget = QWidget()
            crumb_layout = QHBoxLayout(crumb_widget)
            crumb_layout.setContentsMargins(0, 0, 0, 8)
            crumb_layout.setSpacing(8)

            back_btn = QPushButton("◀  Voltar")
            back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            back_btn.setStyleSheet(
                "QPushButton { background: #F5F5F5; border: 1px solid #E8E8E8; "
                "border-radius: 8px; padding: 6px 14px; font-size: 12px; }"
                "QPushButton:hover { background: #FFE4E9; border-color: #FFB6C1; }"
            )
            back_btn.clicked.connect(self._go_root)
            crumb_layout.addWidget(back_btn)

            crumb = QLabel(f"📁  {group}")
            crumb.setStyleSheet("font-size: 13px; font-weight: 600; color: #FF69B4;")
            crumb_layout.addWidget(crumb)
            crumb_layout.addStretch()
            self.videos_container.addWidget(crumb_widget)

        # Pastas (grupos) — só na raiz
        if not group:
            groups = self._list_groups()
            if groups:
                folders_card = SettingCard()
                for g in groups:
                    gpath = os.path.join(root, g)
                    n_videos = len([
                        x for x in os.listdir(gpath)
                        if x.lower().endswith(('.mp4', '.mkv', '.avi', '.webm'))
                    ])

                    gbtns = FlowWidget()

                    open_btn = QPushButton("Abrir")
                    open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    open_btn.setStyleSheet(
                        "QPushButton { background: #FF69B4; border: none; border-radius: 8px; "
                        "padding: 6px 14px; color: white; font-size: 11px; font-weight: 600; }"
                        "QPushButton:hover { background: #FF91A4; }"
                    )
                    open_btn.clicked.connect(lambda checked, name=g: self._open_group(name))
                    gbtns.add_widget(open_btn)

                    grename_btn = QPushButton("Renomear")
                    grename_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    grename_btn.setStyleSheet(
                        "QPushButton { background: #F5F5F5; border: 1px solid #E8E8E8; "
                        "border-radius: 8px; padding: 6px 12px; font-size: 11px; }"
                        "QPushButton:hover { background: #FFE4E9; border-color: #FFB6C1; }"
                    )
                    grename_btn.clicked.connect(lambda checked, name=g: self._rename_group(name))
                    gbtns.add_widget(grename_btn)

                    gdel_btn = QPushButton("Excluir")
                    gdel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    gdel_btn.setStyleSheet(
                        "QPushButton { background: #FFEBEE; border: 1px solid #EF9A9A; "
                        "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                        "color: #C62828; font-weight: 500; }"
                        "QPushButton:hover { background: #FFCDD2; }"
                    )
                    gdel_btn.clicked.connect(lambda checked, name=g: self._delete_group(name))
                    gbtns.add_widget(gdel_btn)

                    plural = "vídeo" if n_videos == 1 else "vídeos"
                    folders_card.add_row(self._make_list_row(
                        f"📁  {g}", f"{n_videos} {plural}", gbtns
                    ))
                self.videos_container.addWidget(folders_card)

        files = [f for f in os.listdir(folder)
                 if f.lower().endswith(('.mp4', '.mkv', '.avi', '.webm'))]
        files.sort(reverse=True)

        if not files:
            no_files = QLabel("Nenhuma gravação nesta pasta.")
            no_files.setStyleSheet("color: #999; font-size: 13px; padding: 20px;")
            no_files.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.videos_container.addWidget(no_files)
            return

        card = SettingCard()
        for f in files:
            filepath = os.path.join(folder, f)
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            video_name = os.path.splitext(f)[0]
            subtitle_path = os.path.join(folder, video_name + ".txt")
            has_subtitle = os.path.isfile(subtitle_path)

            # Container de botões (responsivo — quebra linha se faltar espaço)
            btns_widget = FlowWidget()

            # Botão Assistir
            play_btn = QPushButton("Assistir")
            play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            play_btn.setStyleSheet(
                "QPushButton { background: #FF69B4; border: none; border-radius: 8px; "
                "padding: 6px 14px; color: white; font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { background: #FF91A4; }"
            )
            path = filepath
            sub = subtitle_path if has_subtitle else None
            play_btn.clicked.connect(lambda checked, p=path, s=sub: self._play_video(p, s))
            btns_widget.add_widget(play_btn)

            # Botão Renomear
            rename_btn = QPushButton("Renomear")
            rename_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            rename_btn.setStyleSheet(
                "QPushButton { background: #F5F5F5; border: 1px solid #E8E8E8; "
                "border-radius: 8px; padding: 6px 12px; font-size: 11px; }"
                "QPushButton:hover { background: #FFE4E9; border-color: #FFB6C1; }"
            )
            rename_btn.clicked.connect(lambda checked, p=path: self._rename_video(p))
            btns_widget.add_widget(rename_btn)

            # Botão Legenda
            if has_subtitle:
                sub_btn = QPushButton("Ver Legenda")
                sub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                sub_btn.setStyleSheet(
                    "QPushButton { background: #E8F5E9; border: 1px solid #A5D6A7; "
                    "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                    "color: #2E7D32; font-weight: 500; }"
                    "QPushButton:hover { background: #C8E6C9; }"
                )
                sub_btn.clicked.connect(
                    lambda checked, p=subtitle_path, nm=video_name:
                    self._view_text(p, False, f"Legenda — {nm}")
                )
            else:
                sub_btn = QPushButton("Criar Legenda")
                sub_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                sub_btn.setStyleSheet(
                    "QPushButton { background: #FFF3E0; border: 1px solid #FFCC80; "
                    "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                    "color: #E65100; font-weight: 500; }"
                    "QPushButton:hover { background: #FFE0B2; }"
                )
                sub_btn.clicked.connect(lambda checked, p=path: self._create_subtitle(p))
            btns_widget.add_widget(sub_btn)

            # Botão OCR (texto da tela)
            tela_path = os.path.join(folder, video_name + "_tela.txt")
            has_tela = os.path.isfile(tela_path)
            if has_tela:
                ocr_btn = QPushButton("Ver Texto Tela")
                ocr_btn.setStyleSheet(
                    "QPushButton { background: #E0F2F1; border: 1px solid #80CBC4; "
                    "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                    "color: #00695C; font-weight: 500; }"
                    "QPushButton:hover { background: #B2DFDB; }"
                )
                ocr_btn.clicked.connect(
                    lambda checked, p=tela_path, nm=video_name:
                    self._view_text(p, False, f"Texto da Tela — {nm}")
                )
            else:
                ocr_btn = QPushButton("Ler Tela (OCR)")
                ocr_btn.setStyleSheet(
                    "QPushButton { background: #E0F7FA; border: 1px solid #80DEEA; "
                    "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                    "color: #00838F; font-weight: 500; }"
                    "QPushButton:hover { background: #B2EBF2; }"
                )
                ocr_btn.clicked.connect(lambda checked, p=path: self._ocr_video(p))
            ocr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btns_widget.add_widget(ocr_btn)

            # Botão de resumo IA
            summary_path = os.path.join(folder, video_name + "_resumo.txt")
            has_summary = os.path.isfile(summary_path)
            if has_summary:
                # Já existe resumo → botão para visualizar
                ia_btn = QPushButton("Ver Resumo IA")
                ia_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                ia_btn.setStyleSheet(
                    "QPushButton { background: #D1C4E9; border: 1px solid #B39DDB; "
                    "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                    "color: #4527A0; font-weight: 600; }"
                    "QPushButton:hover { background: #B39DDB; }"
                )
                ia_btn.clicked.connect(
                    lambda checked, sp2=summary_path, nm=video_name:
                    self._view_text(sp2, True, f"Resumo IA — {nm}")
                )
            else:
                # Ainda não há resumo → botão para gerar (só se houver legenda)
                ia_btn = QPushButton("Resumir IA")
                ia_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                ia_btn.setEnabled(has_subtitle)
                if has_subtitle:
                    ia_btn.setStyleSheet(
                        "QPushButton { background: #EDE7F6; border: 1px solid #B39DDB; "
                        "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                        "color: #5E35B1; font-weight: 600; }"
                        "QPushButton:hover { background: #D1C4E9; }"
                    )
                else:
                    ia_btn.setStyleSheet(
                        "QPushButton { background: #F5F5F5; border: 1px solid #E8E8E8; "
                        "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                        "color: #BBBBBB; }"
                    )
                    ia_btn.setToolTip("Crie a legenda antes de resumir com IA")
                ia_btn.clicked.connect(
                    lambda checked, p=path, sp=subtitle_path: self._summarize_ia(p, sp)
                )
            btns_widget.add_widget(ia_btn)

            # Botão Chat (perguntar à IA sobre o vídeo) — precisa de legenda
            chat_btn = QPushButton("Chat")
            chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            chat_btn.setEnabled(has_subtitle)
            if has_subtitle:
                chat_btn.setStyleSheet(
                    "QPushButton { background: #FFF3E0; border: 1px solid #FFB74D; "
                    "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                    "color: #E65100; font-weight: 600; }"
                    "QPushButton:hover { background: #FFE0B2; }"
                )
                chat_btn.clicked.connect(
                    lambda checked, p=path, sp=subtitle_path: self._open_chat(p, sp)
                )
            else:
                chat_btn.setStyleSheet(
                    "QPushButton { background: #F5F5F5; border: 1px solid #E8E8E8; "
                    "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                    "color: #BBBBBB; }"
                )
                chat_btn.setToolTip("Crie a legenda antes de conversar com a IA")
            btns_widget.add_widget(chat_btn)

            # Botão Relatório Completo (ou Ver Relatório se já existe)
            report_path = os.path.join(folder, video_name + "_relatorio.md")
            if os.path.isfile(report_path):
                report_btn = QPushButton("Ver Relatório")
                report_btn.setStyleSheet(
                    "QPushButton { background: #FCE4EC; border: 1px solid #F48FB1; "
                    "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                    "color: #AD1457; font-weight: 700; }"
                    "QPushButton:hover { background: #F8BBD0; }"
                )
                report_btn.clicked.connect(
                    lambda checked, rp=report_path, nm=video_name:
                    self._view_report(rp, nm)
                )
            else:
                report_btn = QPushButton("★ Relatório Completo")
                report_btn.setStyleSheet(
                    "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
                    "stop:0 #FF69B4, stop:1 #BA68C8); border: none; "
                    "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                    "color: white; font-weight: 700; }"
                    "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
                    "stop:0 #FF91A4, stop:1 #CE93D8); }"
                )
                report_btn.clicked.connect(lambda checked, p=path: self._full_report(p))
            report_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btns_widget.add_widget(report_btn)

            # Botão Mover
            move_btn = QPushButton("Mover")
            move_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            move_btn.setStyleSheet(
                "QPushButton { background: #E3F2FD; border: 1px solid #90CAF9; "
                "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                "color: #1565C0; font-weight: 500; }"
                "QPushButton:hover { background: #BBDEFB; }"
            )
            move_btn.clicked.connect(lambda checked, p=path: self._move_video(p))
            btns_widget.add_widget(move_btn)

            # Botão Excluir
            del_btn = QPushButton("Excluir")
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet(
                "QPushButton { background: #FFEBEE; border: 1px solid #EF9A9A; "
                "border-radius: 8px; padding: 6px 12px; font-size: 11px; "
                "color: #C62828; font-weight: 500; }"
                "QPushButton:hover { background: #FFCDD2; }"
            )
            del_btn.clicked.connect(lambda checked, p=path: self._delete_video(p))
            btns_widget.add_widget(del_btn)

            # Descrição com status de transcrição
            desc = f"{size_mb:.1f} MB"
            if has_subtitle:
                desc += "  •  Legenda disponível"
            if has_summary:
                desc += "  •  Resumo IA disponível"

            # Verifica se está transcrevendo este vídeo
            if hasattr(self, '_transcribing_video') and self._transcribing_video == filepath:
                desc += "  •  Transcrevendo..."

            audio_bar = AudioPlayerBar(filepath, self)
            card.add_row(self._make_list_row(f, desc, btns_widget, audio_bar))

        self.videos_container.addWidget(card)

    def _play_video(self, video_path, subtitle_path=None):
        """Abre o player de vídeo embutido."""
        self.video_player.load_video(video_path, subtitle_path)

    def _rename_video(self, video_path):
        """Renomeia vídeo (e legenda se existir)."""
        import os
        old_name = os.path.splitext(os.path.basename(video_path))[0]
        ext = os.path.splitext(video_path)[1]
        folder = os.path.dirname(video_path)

        new_name, ok = QInputDialog.getText(
            self, "Renomear Vídeo",
            "Novo nome (sem extensão):",
            QLineEdit.EchoMode.Normal,
            old_name
        )

        if ok and new_name and new_name != old_name:
            new_name = new_name.strip()
            # Caracteres inválidos
            invalid = '<>:"/\\|?*'
            for c in invalid:
                new_name = new_name.replace(c, "_")

            new_video_path = os.path.join(folder, new_name + ext)

            if os.path.exists(new_video_path):
                QMessageBox.warning(self, "Erro", "Já existe um arquivo com esse nome.")
                return

            try:
                # Renomeia vídeo
                os.rename(video_path, new_video_path)

                # Renomeia arquivos associados, se existirem.
                for suffix in SIDECAR_SUFFIXES:
                    old_side = os.path.join(folder, old_name + suffix)
                    if os.path.isfile(old_side):
                        os.rename(old_side, os.path.join(folder, new_name + suffix))

                # Renomeia a pasta de imagens do relatório e corrige os links
                old_img = os.path.join(folder, old_name + REPORT_IMG_SUFFIX)
                new_img = os.path.join(folder, new_name + REPORT_IMG_SUFFIX)
                if os.path.isdir(old_img):
                    os.rename(old_img, new_img)
                    report_md = os.path.join(folder, new_name + "_relatorio.md")
                    if os.path.isfile(report_md):
                        try:
                            with open(report_md, "r", encoding="utf-8") as f:
                                md = f.read()
                            md = md.replace(old_name + REPORT_IMG_SUFFIX,
                                            new_name + REPORT_IMG_SUFFIX)
                            with open(report_md, "w", encoding="utf-8") as f:
                                f.write(md)
                        except Exception:
                            pass

                self._refresh_videos_list()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao renomear: {str(e)}")

    # =================== GRUPOS / PASTAS ===================
    def _go_root(self):
        self._current_group = None
        self._refresh_videos_list()

    def _open_group(self, name):
        self._current_group = name
        self._refresh_videos_list()

    def _sanitize_name(self, name):
        name = (name or "").strip()
        for c in '<>:"/\\|?*':
            name = name.replace(c, "_")
        return name

    def _create_group_folder(self):
        """Cria uma nova pasta (grupo) dentro da pasta de saída."""
        import os
        root = self.config.get("output_folder")
        if not os.path.isdir(root):
            QMessageBox.warning(self, "Erro", "Pasta de saída não encontrada.")
            return

        name, ok = QInputDialog.getText(
            self, "Nova Pasta", "Nome da pasta:", QLineEdit.EchoMode.Normal, ""
        )
        if not (ok and name.strip()):
            return
        name = self._sanitize_name(name)
        new_path = os.path.join(root, name)
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Erro", "Já existe uma pasta com esse nome.")
            return
        try:
            os.makedirs(new_path)
            # Se estiver dentro de um grupo, volta para a raiz para exibir a nova pasta
            self._current_group = None
            self._refresh_videos_list()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao criar pasta: {str(e)}")

    def _rename_group(self, name):
        import os
        root = self.config.get("output_folder")
        new_name, ok = QInputDialog.getText(
            self, "Renomear Pasta", "Novo nome:", QLineEdit.EchoMode.Normal, name
        )
        if not (ok and new_name.strip() and new_name.strip() != name):
            return
        new_name = self._sanitize_name(new_name)
        new_path = os.path.join(root, new_name)
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Erro", "Já existe uma pasta com esse nome.")
            return
        try:
            os.rename(os.path.join(root, name), new_path)
            self._refresh_videos_list()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao renomear pasta: {str(e)}")

    def _delete_group(self, name):
        import os
        import shutil
        root = self.config.get("output_folder")
        gpath = os.path.join(root, name)
        n_items = len(os.listdir(gpath)) if os.path.isdir(gpath) else 0

        if n_items:
            msg = (
                f"A pasta \"{name}\" contém {n_items} arquivo(s). "
                "Excluir a pasta apagará todo o conteúdo dela. Deseja continuar?"
            )
        else:
            msg = f"Excluir a pasta \"{name}\"?"
        reply = QMessageBox.question(
            self, "Excluir Pasta", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.rmtree(gpath)
            if getattr(self, "_current_group", None) == name:
                self._current_group = None
            self._refresh_videos_list()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao excluir pasta: {str(e)}")

    def _move_video(self, video_path):
        """Move o vídeo (com legenda e resumo) para outra pasta/grupo."""
        import os
        import shutil
        root = self.config.get("output_folder")
        src_folder = os.path.dirname(video_path)
        base = os.path.splitext(os.path.basename(video_path))[0]

        groups = self._list_groups()
        # Monta destinos: Raiz + grupos, excluindo a pasta atual
        options = []
        mapping = {}
        current_group = getattr(self, "_current_group", None)
        if current_group is not None:
            options.append("📂 Principal (raiz)")
            mapping["📂 Principal (raiz)"] = root
        for g in groups:
            if g == current_group:
                continue
            label = f"📁 {g}"
            options.append(label)
            mapping[label] = os.path.join(root, g)

        if not options:
            QMessageBox.information(
                self, "Mover",
                "Nenhuma pasta de destino disponível. Crie uma pasta primeiro "
                "com \"Nova Pasta\"."
            )
            return

        choice, ok = QInputDialog.getItem(
            self, "Mover Vídeo", "Mover para:", options, 0, False
        )
        if not (ok and choice):
            return
        dest_folder = mapping[choice]

        # Arquivos a mover: vídeo + todos os associados
        ext = os.path.splitext(video_path)[1]
        to_move = [base + ext] + [base + s for s in SIDECAR_SUFFIXES]
        # Checa colisões
        for fname in to_move:
            src = os.path.join(src_folder, fname)
            if os.path.isfile(src) and os.path.exists(os.path.join(dest_folder, fname)):
                QMessageBox.warning(
                    self, "Erro",
                    f"Já existe um arquivo \"{fname}\" na pasta de destino."
                )
                return
        try:
            for fname in to_move:
                src = os.path.join(src_folder, fname)
                if os.path.isfile(src):
                    shutil.move(src, os.path.join(dest_folder, fname))
            # Move a pasta de imagens do relatório, se existir
            img_dir = os.path.join(src_folder, base + REPORT_IMG_SUFFIX)
            if os.path.isdir(img_dir):
                dest_img = os.path.join(dest_folder, base + REPORT_IMG_SUFFIX)
                if not os.path.exists(dest_img):
                    shutil.move(img_dir, dest_img)
            self._refresh_videos_list()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao mover: {str(e)}")

    def _create_subtitle(self, video_path):
        """Inicia transcrição LOCAL (offline) do vídeo com Parakeet V3."""
        if not LocalTranscriber.available():
            QMessageBox.warning(
                self, "Indisponível",
                "A transcrição local não está disponível nesta versão."
            )
            return

        detail = (
            "Transcrição LOCAL (offline) com Parakeet V3.\n"
            "Na primeira vez o modelo será baixado (~600 MB, pode demorar)."
        )
        reply = QMessageBox.question(
            self, "Criar Legenda",
            f"Iniciar transcrição de:\n{os.path.basename(video_path)}\n\n{detail}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._transcribing_video = video_path
            self.transcribe_status.show()
            self.transcribe_progress.show()
            self.transcribe_status.setText("Transcrevendo...")
            self.transcribe_progress.setValue(0)
            self._refresh_videos_list()
            self.local_transcriber.transcribe(video_path)

    def _delete_video(self, video_path):
        """Exclui o vídeo (e legenda/resumo associados, se existirem)."""
        import os
        name = os.path.basename(video_path)
        reply = QMessageBox.question(
            self, "Excluir Vídeo",
            f"Tem certeza que deseja excluir?\n\n{name}\n\n"
            "A legenda e o resumo associados também serão removidos. "
            "Esta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        folder = os.path.dirname(video_path)
        base = os.path.splitext(os.path.basename(video_path))[0]
        targets = [video_path] + [
            os.path.join(folder, base + s) for s in SIDECAR_SUFFIXES
        ]
        try:
            for t in targets:
                if os.path.isfile(t):
                    os.remove(t)
            img_dir = os.path.join(folder, base + REPORT_IMG_SUFFIX)
            if os.path.isdir(img_dir):
                import shutil
                shutil.rmtree(img_dir, ignore_errors=True)
            self._refresh_videos_list()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao excluir: {str(e)}")

    def _summarize_ia(self, video_path, subtitle_path):
        """Envia a legenda ao provedor de IA e salva o resumo em .txt."""
        import os
        if not os.path.isfile(subtitle_path):
            QMessageBox.warning(
                self, "Sem Legenda",
                "Este vídeo ainda não tem legenda. Crie a legenda primeiro."
            )
            return

        provider = self.config.get("ia_provider", "")
        model = self.config.get("ia_model", "")
        api_key = self.config.get("ia_api_key", "")

        if not provider.strip():
            QMessageBox.warning(
                self, "IA não configurada",
                "Nenhum provedor selecionado. Vá na aba IA e escolha o provedor."
            )
            return

        if not api_key.strip():
            QMessageBox.warning(
                self, "IA não configurada",
                "Nenhuma API key configurada. Vá na aba IA, escolha o provedor e "
                "informe a sua API key."
            )
            return

        try:
            with open(subtitle_path, "r", encoding="utf-8") as f:
                subtitle_text = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao ler a legenda: {str(e)}")
            return

        if not subtitle_text.strip():
            QMessageBox.warning(self, "Legenda vazia", "A legenda está vazia.")
            return

        # Feedback visual
        self.transcribe_status.show()
        self.transcribe_progress.show()
        self.transcribe_progress.setRange(0, 0)  # indeterminado
        self.transcribe_status.setText("Gerando resumo com IA...")
        self.transcribe_status.setStyleSheet("color: #5E35B1; font-size: 12px; font-weight: 600;")

        template_key = self.config.get("ia_template", "geral")
        instructions = summary_templates.instructions_for(template_key)

        self._ia_worker = SummarizeWorker(
            provider, model, api_key, subtitle_text, video_path,
            template_instructions=instructions
        )
        self._ia_worker.finished_ok.connect(self._on_summary_finished)
        self._ia_worker.failed.connect(self._on_summary_error)
        self._ia_worker.start()

    def _on_summary_finished(self, summary, video_path):
        import os
        self.transcribe_progress.setRange(0, 100)
        self.transcribe_progress.hide()

        folder = os.path.dirname(video_path)
        base = os.path.splitext(os.path.basename(video_path))[0]
        out_path = os.path.join(folder, base + "_resumo.txt")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(summary)
        except Exception as e:
            self._on_summary_error(f"Erro ao salvar o resumo: {str(e)}", video_path)
            return

        self.transcribe_status.setText(f"Resumo salvo: {os.path.basename(out_path)}")
        self.transcribe_status.setStyleSheet("color: #2E7D32; font-size: 12px; font-weight: 600;")
        self._refresh_videos_list()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(6000, lambda: (
            self.transcribe_status.hide(),
            self.transcribe_status.setStyleSheet("color: #FF69B4; font-size: 12px;")
        ))

    def _on_summary_error(self, msg, video_path=None):
        self.transcribe_progress.setRange(0, 100)
        self.transcribe_progress.hide()
        self.transcribe_status.setText(f"Erro no resumo: {msg}")
        self.transcribe_status.setStyleSheet("color: #D32F2F; font-size: 12px; font-weight: 600;")
        QMessageBox.critical(self, "Erro no Resumo IA", msg)

    def _on_transcribe_progress(self, current, total):
        self.transcribe_progress.setMaximum(total)
        self.transcribe_progress.setValue(current)

    def _on_transcribe_finished(self, txt_path):
        self._transcribing_video = None
        self.transcribe_progress.hide()

        # Reabilita o botão de download e atualiza status do modelo
        if hasattr(self, "parakeet_dl_btn"):
            self.parakeet_dl_btn.setEnabled(True)
            self._update_parakeet_status()

        if not txt_path:
            # Conclusão de download do modelo (sem legenda)
            self.transcribe_status.setText("Modelo Parakeet pronto!")
        else:
            self.transcribe_status.setText(f"Legenda salva: {os.path.basename(txt_path)}")
        self.transcribe_status.setStyleSheet("color: #2E7D32; font-size: 12px; font-weight: 600;")
        self._refresh_videos_list()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(5000, lambda: (
            self.transcribe_status.hide(),
            self.transcribe_status.setStyleSheet("color: #FF69B4; font-size: 12px;")
        ))

    def _on_transcribe_error(self, msg):
        self._transcribing_video = None
        self.transcribe_status.setText(f"Erro: {msg}")
        self.transcribe_status.setStyleSheet("color: #D32F2F; font-size: 12px; font-weight: 600;")
        self.transcribe_progress.hide()
        if hasattr(self, "parakeet_dl_btn"):
            self.parakeet_dl_btn.setEnabled(True)
            self._update_parakeet_status()
        self._refresh_videos_list()
        QMessageBox.critical(self, "Erro na Transcrição", msg)

    def _on_transcribe_status(self, msg):
        self.transcribe_status.setText(msg)

    # =================== SOBRE ===================
    def _create_about_page(self):
        scroll, layout = self._make_scroll_page()

        layout.addWidget(SectionTitle("SOBRE"))

        card = SettingCard()
        card.add_row(SettingRow("Versão", QLabel("1.0.0")))
        card.add_row(SettingRow("Motor de Gravação", QLabel("FFmpeg")))
        card.add_row(SettingRow("Interface", QLabel("PyQt6")))
        card.add_row(SettingRow("Plataforma", QLabel("Windows")))
        layout.addWidget(card)

        layout.addSpacing(20)

        desc = QLabel(
            "Screvo é um gravador de tela leve que também transcreve o áudio "
            "e resume com IA.\n"
            "Capture sua tela e áudio do sistema com facilidade.\n\n"
            "Pressione o atalho configurado para iniciar a gravação."
        )
        desc.setStyleSheet(
            "color: #666; font-size: 13px; padding: 20px; line-height: 1.6; "
            "background: #FFF5F7; border-radius: 10px; border: 1px solid #FFE4E9;"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addStretch()
        return scroll

    # =================== ACTIONS ===================
    def _save_setting(self, key, value):
        self.config.set(key, value)
        self.settings_changed.emit()

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Selecionar Pasta de Gravação",
            self.config.get("output_folder")
        )
        if folder:
            self.folder_input.setText(folder)
            self._save_setting("output_folder", folder)

    def _capture_hotkey(self):
        """Captura novo atalho do teclado."""
        self.hotkey_btn.setText("Pressione o atalho...")
        self.hotkey_btn.setStyleSheet(
            "QPushButton { background-color: #FFE4E9; border: 2px solid #FF69B4; "
            "border-radius: 8px; padding: 8px 16px; font-weight: 500; min-width: 140px; "
            "color: #FF69B4; }"
        )
        self._capturing_hotkey = True
        self.hotkey_btn.setFocus()
        self.grabKeyboard()

    def keyPressEvent(self, event):
        if hasattr(self, '_capturing_hotkey') and self._capturing_hotkey:
            modifiers = []
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                modifiers.append("ctrl")
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                modifiers.append("shift")
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                modifiers.append("alt")

            key = event.key()
            key_name = None

            # Mapear tecla
            key_map = {
                Qt.Key.Key_Space: "space",
                Qt.Key.Key_Return: "enter",
                Qt.Key.Key_Escape: "escape",
                Qt.Key.Key_Tab: "tab",
                Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", Qt.Key.Key_F3: "f3",
                Qt.Key.Key_F4: "f4", Qt.Key.Key_F5: "f5", Qt.Key.Key_F6: "f6",
                Qt.Key.Key_F7: "f7", Qt.Key.Key_F8: "f8", Qt.Key.Key_F9: "f9",
                Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
            }

            if key in key_map:
                key_name = key_map[key]
            elif Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
                key_name = chr(key).lower()
            elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
                key_name = chr(key)

            if key_name and modifiers:
                hotkey = "+".join(modifiers + [key_name])
                self._set_hotkey(hotkey)
                self.releaseKeyboard()
                self._capturing_hotkey = False
                return
            elif key == Qt.Key.Key_Escape:
                # Cancela captura
                self.releaseKeyboard()
                self._capturing_hotkey = False
                self.hotkey_btn.setText(
                    self.config.get("hotkey").replace("+", " + ").title()
                )
                self.hotkey_btn.setStyleSheet(
                    "QPushButton { background-color: #F5F5F5; border: 1px solid #E8E8E8; "
                    "border-radius: 8px; padding: 8px 16px; font-weight: 500; min-width: 140px; }"
                    "QPushButton:hover { border-color: #FFB6C1; }"
                )
                return

        super().keyPressEvent(event)

    def _set_hotkey(self, hotkey):
        self.config.set("hotkey", hotkey)
        self.hotkey_btn.setText(hotkey.replace("+", " + ").title())
        self.hotkey_btn.setStyleSheet(
            "QPushButton { background-color: #F5F5F5; border: 1px solid #E8E8E8; "
            "border-radius: 8px; padding: 8px 16px; font-weight: 500; min-width: 140px; }"
            "QPushButton:hover { border-color: #FFB6C1; }"
        )
        self.hotkey_changed.emit(hotkey)

    def _on_volume_changed(self, value):
        self.volume_label.setText(f"{value}%")
        self._save_setting("volume", value)

    def _on_audio_mode_changed(self, index):
        mode = self.audio_mode_combo.itemData(index)
        if mode:
            self._save_setting("audio_mode", mode)

    def _on_audio_device_changed(self, index):
        device = self.audio_combo.itemData(index)
        if device:
            self._save_setting("audio_device", device)

    def _refresh_audio_devices(self):
        """Enumera os microfones em background e atualiza a combo."""
        import threading
        from recorder import Recorder

        def worker():
            try:
                devices = Recorder.list_audio_devices(force=True)
            except Exception:
                devices = []
            self._audio_devices_loaded.emit(devices)

        threading.Thread(target=worker, daemon=True).start()

    def _populate_audio_combo(self, devices):
        """Preenche a combo de áudio (executa na main thread via sinal)."""
        self.audio_combo.blockSignals(True)
        self.audio_combo.clear()
        self.audio_combo.addItem("Automático (primeiro microfone)", "auto")
        for d in devices:
            self.audio_combo.addItem(d, d)

        # Seleciona o salvo (ou "auto" por padrão)
        saved = self.config.get("audio_device", "auto")
        idx = self.audio_combo.findData(saved)
        self.audio_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.audio_combo.blockSignals(False)

        # Atualiza o indicador de "som do sistema" (loopback)
        if hasattr(self, "loopback_status"):
            from recorder import Recorder
            from audio_capture import SystemAudioCapture
            lb = Recorder._find_loopback_device(devices)

            def _green(txt):
                self.loopback_status.setText(txt)
                self.loopback_status.setStyleSheet(
                    "color: #2E7D32; font-size: 12px; padding: 10px; "
                    "background: #E8F5E9; border-radius: 8px; border: 1px solid #A5D6A7;"
                )

            def _orange(txt):
                self.loopback_status.setText(txt)
                self.loopback_status.setStyleSheet(
                    "color: #E65100; font-size: 12px; padding: 10px; "
                    "background: #FFF3E0; border-radius: 8px; border: 1px solid #FFCC80;"
                )

            if SystemAudioCapture.available():
                _green("✅ Som do sistema é capturado automaticamente (WASAPI, "
                       "sem precisar instalar nada).")
            elif lb:
                _green(f"✅ Som do sistema disponível via: {lb}")
            else:
                _orange("⏳ Componente de captura do som do sistema ainda não "
                        "instalado. Ele é baixado automaticamente ao abrir o app "
                        "(precisa de internet). Reinicie o app uma vez; até lá, só "
                        "o microfone será gravado.")

    def _on_startup_changed(self, checked):
        self._save_setting("start_with_windows", checked)
        # Registra/remove do startup do Windows
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if checked:
                import sys
                exe = sys.executable
                winreg.SetValueEx(key, "VideoRecorder", 0, winreg.REG_SZ, f'"{exe}"')
            else:
                try:
                    winreg.DeleteValue(key, "VideoRecorder")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass

    @staticmethod
    def _open_path_async(path):
        """Abre um arquivo/pasta sem bloquear a interface.

        os.startfile (ShellExecute) pode travar a thread principal quando o
        shell está ocupado (ex.: com o player de áudio ativo). Rodamos numa
        thread separada para a UI não congelar.
        """
        import os
        import threading

        def _open():
            try:
                os.startfile(path)
            except Exception:
                pass

        threading.Thread(target=_open, daemon=True).start()

    def _open_file(self, path):
        self._open_path_async(path)

    def _view_text(self, path, is_markdown=False, title=None):
        """Abre uma janela interna exibindo o conteúdo do arquivo (texto/Markdown)."""
        import os
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao abrir o arquivo: {str(e)}")
            return
        dlg = TextViewerDialog(
            title or os.path.basename(path), content, is_markdown, path, self
        )
        dlg.exec()

    def _open_chat(self, video_path, subtitle_path):
        """Abre o chat de perguntas sobre o vídeo (usa a legenda como contexto)."""
        import os
        if not os.path.isfile(subtitle_path):
            QMessageBox.warning(self, "Sem Legenda",
                                "Crie a legenda antes de conversar com a IA.")
            return
        provider = self.config.get("ia_provider", "")
        model = self.config.get("ia_model", "")
        api_key = self.config.get("ia_api_key", "")
        if not provider.strip() or not api_key.strip():
            QMessageBox.warning(
                self, "IA não configurada",
                "Configure o provedor e a API key na aba IA."
            )
            return
        try:
            with open(subtitle_path, "r", encoding="utf-8") as f:
                transcript = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao ler a legenda: {str(e)}")
            return

        nm = os.path.splitext(os.path.basename(video_path))[0]
        dlg = ChatDialog(f"Chat — {nm}", transcript, provider, model, api_key, self)
        dlg.exec()

    def _ocr_video(self, video_path):
        """Extrai o texto que aparece na tela do vídeo (OCR local)."""
        import os
        reply = QMessageBox.question(
            self, "Ler Texto da Tela (OCR)",
            f"Extrair o texto que aparece na tela de:\n{os.path.basename(video_path)}\n\n"
            "Isso analisa frames do vídeo localmente e pode demorar em vídeos "
            "longos. Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.transcribe_status.show()
        self.transcribe_progress.show()
        self.transcribe_progress.setRange(0, 0)
        self.transcribe_status.setText("Lendo texto da tela (OCR)...")
        self.transcribe_status.setStyleSheet("color: #00838F; font-size: 12px; font-weight: 600;")

        self._ocr_worker = OcrWorker(video_path)
        self._ocr_worker.progress.connect(self._on_ocr_progress)
        self._ocr_worker.status.connect(lambda m: self.transcribe_status.setText(m))
        self._ocr_worker.finished_ok.connect(self._on_ocr_finished)
        self._ocr_worker.failed.connect(self._on_ocr_error)
        self._ocr_worker.start()

    def _on_ocr_progress(self, current, total):
        self.transcribe_progress.setRange(0, total)
        self.transcribe_progress.setValue(current)

    def _on_ocr_finished(self, txt_path, video_path):
        import os
        self.transcribe_progress.setRange(0, 100)
        self.transcribe_progress.hide()
        self.transcribe_status.setText(f"Texto da tela salvo: {os.path.basename(txt_path)}")
        self.transcribe_status.setStyleSheet("color: #2E7D32; font-size: 12px; font-weight: 600;")
        self._refresh_videos_list()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(6000, lambda: (
            self.transcribe_status.hide(),
            self.transcribe_status.setStyleSheet("color: #FF69B4; font-size: 12px;")
        ))

    def _on_ocr_error(self, msg, video_path=None):
        self.transcribe_progress.setRange(0, 100)
        self.transcribe_progress.hide()
        self.transcribe_status.setText(f"Erro no OCR: {msg}")
        self.transcribe_status.setStyleSheet("color: #D32F2F; font-size: 12px; font-weight: 600;")
        QMessageBox.critical(self, "Erro no OCR", msg)

    # =================== RELATÓRIO ===================
    def _view_report(self, report_path, video_name):
        """Abre o relatório (Markdown com imagens) no visualizador."""
        import os
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao abrir o relatório: {str(e)}")
            return
        dlg = TextViewerDialog(
            f"Relatório — {video_name}", content, is_markdown=True,
            file_path=report_path, parent=self,
            base_dir=os.path.dirname(report_path),
        )
        dlg.exec()

    def _full_report(self, video_path):
        """Gera o relatório completo: legenda -> OCR -> resumo IA com capturas."""
        provider = self.config.get("ia_provider", "")
        model = self.config.get("ia_model", "")
        api_key = self.config.get("ia_api_key", "")
        if not provider.strip() or not api_key.strip():
            QMessageBox.warning(
                self, "IA não configurada",
                "Configure o provedor e a API key na aba IA antes de gerar o relatório."
            )
            return
        if not LocalTranscriber.available():
            QMessageBox.warning(self, "Indisponível",
                                "A transcrição local não está disponível.")
            return

        import os
        reply = QMessageBox.question(
            self, "Relatório Completo",
            f"Gerar o relatório completo de:\n{os.path.basename(video_path)}\n\n"
            "Etapas: criar legenda → ler tela (OCR) → montar relatório com IA "
            "(inserindo capturas do vídeo). Pode demorar. Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.transcribe_status.show()
        self.transcribe_progress.show()
        self.transcribe_progress.setRange(0, 0)
        self.transcribe_status.setText("Gerando relatório completo...")
        self.transcribe_status.setStyleSheet("color: #AD1457; font-size: 12px; font-weight: 600;")

        self._report_worker = ReportWorker(video_path, provider, model, api_key)
        self._report_worker.status.connect(lambda m: self.transcribe_status.setText(m))
        self._report_worker.progress.connect(self._on_ocr_progress)
        self._report_worker.finished_ok.connect(self._on_report_finished)
        self._report_worker.failed.connect(self._on_report_error)
        self._report_worker.start()

    def _on_report_finished(self, report_path, video_path):
        import os
        self.transcribe_progress.setRange(0, 100)
        self.transcribe_progress.hide()
        self.transcribe_status.setText(f"Relatório salvo: {os.path.basename(report_path)}")
        self.transcribe_status.setStyleSheet("color: #2E7D32; font-size: 12px; font-weight: 600;")
        self._refresh_videos_list()
        nm = os.path.splitext(os.path.basename(video_path))[0]
        self._view_report(report_path, nm)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(6000, lambda: (
            self.transcribe_status.hide(),
            self.transcribe_status.setStyleSheet("color: #FF69B4; font-size: 12px;")
        ))

    def _on_report_error(self, msg, video_path=None):
        self.transcribe_progress.setRange(0, 100)
        self.transcribe_progress.hide()
        self.transcribe_status.setText(f"Erro no relatório: {msg}")
        self.transcribe_status.setStyleSheet("color: #D32F2F; font-size: 12px; font-weight: 600;")
        QMessageBox.critical(self, "Erro no Relatório", msg)

    # =================== ÁUDIO (player único, persistente) ===================
    def _ensure_audio_player(self):
        if getattr(self, "_audio_player", None) is None:
            from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
            self._audio_out = QAudioOutput()
            self._audio_player = QMediaPlayer()
            self._audio_player.setAudioOutput(self._audio_out)
            self._audio_player.positionChanged.connect(self._audio_on_pos)
            self._audio_player.durationChanged.connect(self._audio_on_dur)
            self._audio_player.playbackStateChanged.connect(self._audio_on_state)
            self._audio_bar = None
            self._audio_path = None
        return self._audio_player

    def play_audio_toggle(self, bar, path):
        from PyQt6.QtMultimedia import QMediaPlayer
        from PyQt6.QtCore import QUrl
        p = self._ensure_audio_player()
        if self._audio_path != path:
            # Troca de faixa
            self._reset_audio_bar()
            self._audio_bar = bar
            self._audio_path = path
            p.setSource(QUrl.fromLocalFile(path))
            p.play()
        else:
            self._audio_bar = bar
            if p.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                p.pause()
            else:
                p.play()

    def audio_seek(self, pos):
        p = getattr(self, "_audio_player", None)
        if p is not None:
            p.setPosition(pos)

    def bind_existing_audio(self, bar, path):
        """Ao recriar a lista, reflete o estado se esta faixa é a que toca."""
        from PyQt6.QtMultimedia import QMediaPlayer
        p = getattr(self, "_audio_player", None)
        if p is not None and getattr(self, "_audio_path", None) == path:
            self._audio_bar = bar
            try:
                bar.set_range(p.duration())
                bar.set_position(p.position(), p.duration())
                bar.set_playing(
                    p.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                )
            except RuntimeError:
                self._audio_bar = None

    def _reset_audio_bar(self):
        self._safe_audio_bar(lambda b: b.set_playing(False))

    def _safe_audio_bar(self, fn):
        b = getattr(self, "_audio_bar", None)
        if b is None:
            return
        try:
            fn(b)
        except RuntimeError:
            # A barra (widget) foi destruída na recriação da lista.
            self._audio_bar = None

    def _audio_on_pos(self, pos):
        p = self._audio_player
        self._safe_audio_bar(lambda b: b.set_position(pos, p.duration()))

    def _audio_on_dur(self, dur):
        self._safe_audio_bar(lambda b: b.set_range(dur))

    def _audio_on_state(self, state):
        from PyQt6.QtMultimedia import QMediaPlayer
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._safe_audio_bar(lambda b: b.set_playing(playing))

    def _open_output_folder(self):
        import os
        folder = self._current_folder()
        if os.path.isdir(folder):
            self._open_path_async(folder)

    def _load_settings(self):
        """Carrega configurações nos widgets."""
        pass  # Já carregadas no __init__ de cada widget

    _COMBO_VIEW_QSS = """
        QListView {
            background-color: #FFFFFF;
            color: #333333;
            border: 1px solid #FFE4E9;
            border-radius: 8px;
            outline: none;
            padding: 4px;
        }
        QListView::item {
            min-height: 30px;
            padding: 5px 10px;
            border-radius: 6px;
            color: #333333;
            background-color: #FFFFFF;
        }
        QListView::item:hover {
            background-color: #FFF5F7;
            color: #333333;
        }
        QListView::item:selected {
            background-color: #FFE4E9;
            color: #FF69B4;
        }
    """

    def _style_combo_popups(self):
        """Força uma view branca (QListView estilizado) em todas as combos.

        O popup nativo do Windows aparece escuro; com um QListView estilizado
        diretamente, a lista abre branca, seguindo o tema do app.
        """
        for combo in self.findChildren(_QComboBox):
            view = QListView()
            view.setStyleSheet(self._COMBO_VIEW_QSS)
            combo.setView(view)

    def closeEvent(self, event):
        """Minimiza para bandeja em vez de fechar."""
        event.ignore()
        self.hide()
