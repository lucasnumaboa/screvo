"""
Aplicação principal — gerencia system tray, hotkey global, e ciclo de gravação.
"""

import sys
import os
import threading
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction

from config import Config, get_ffmpeg_path
from recorder import Recorder
from settings_window import SettingsWindow
from overlay_widget import OverlayWidget
from monitor_selector import MonitorSelector
from icons import make_app_icon


class HotkeySignal(QObject):
    """Bridge para emitir sinais Qt de threads de hotkey."""
    triggered = pyqtSignal()


class StopSignal(QObject):
    """Bridge para retornar à main thread quando a gravação termina de salvar."""
    done = pyqtSignal(object)


class ScrevoApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName("Screvo")
        self.app.setWindowIcon(make_app_icon(256))

        # Config
        self.config = Config()

        # Recorder
        self.recorder = Recorder(self.config)

        # Hotkey signal bridge
        self.hotkey_signal = HotkeySignal()
        self.hotkey_signal.triggered.connect(self._on_hotkey)

        # Stop signal bridge (thread de salvamento -> main thread)
        self.stop_signal = StopSignal()
        self.stop_signal.done.connect(self._on_stop_complete)

        # UI components
        self.settings_window = SettingsWindow(self.config)
        self.settings_window.hotkey_changed.connect(self._register_hotkey)
        self.settings_window.settings_changed.connect(self._on_settings_changed)

        self.overlay = OverlayWidget()
        self.overlay.record_clicked.connect(self._on_overlay_record)
        self.overlay.pause_clicked.connect(self._on_overlay_pause)
        self.overlay.stop_clicked.connect(self._on_overlay_stop)
        self.overlay.close_clicked.connect(self._on_overlay_close)
        self.overlay.marker_clicked.connect(self._on_overlay_marker)
        self.overlay._update_requested.connect(self._update_overlay_time)

        self.monitor_selector = MonitorSelector()
        self.monitor_selector.monitor_selected.connect(self._on_monitor_selected)
        self.monitor_selector.window_selected.connect(self._on_window_selected)
        self.monitor_selector.region_requested.connect(self._on_region_requested)
        self.monitor_selector.cancelled.connect(self._on_monitor_cancelled)

        from region_selector import RegionSelector
        self.region_selector = RegionSelector()
        self.region_selector.region_selected.connect(self._on_region_selected)
        self.region_selector.cancelled.connect(self._on_monitor_cancelled)

        # Timer para atualizar tempo no overlay
        self._time_timer = QTimer()
        self._time_timer.timeout.connect(self._update_overlay_time)
        self._time_timer.setInterval(500)

        # System tray
        self._setup_tray()

        # Registra hotkey
        self._hotkey_thread = None
        self._register_hotkey(self.config.get("hotkey", "ctrl+shift+r"))

        # Verifica FFmpeg
        if not get_ffmpeg_path():
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                None, "FFmpeg não encontrado",
                "FFmpeg não foi encontrado.\n"
                "Verifique se está na pasta ffmpeg/bin/ do aplicativo ou no PATH do sistema."
            )

    def _create_tray_icon(self):
        """Ícone do app (Screvo) para a bandeja."""
        return make_app_icon(64)

    def _create_recording_icon(self):
        """Ícone vermelho durante gravação."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#FF1744"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawRect(11, 11, 10, 10)
        painter.end()
        return QIcon(pixmap)

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self._create_tray_icon(), self.app)
        self.tray_icon.setToolTip("Screvo")

        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background: white; border: 1px solid #E8E8E8; border-radius: 8px; padding: 4px; }"
            "QMenu::item { padding: 8px 20px; border-radius: 6px; }"
            "QMenu::item:selected { background: #FFE4E9; }"
        )

        show_action = QAction("⚙  Configurações", menu)
        show_action.triggered.connect(self._show_settings)
        menu.addAction(show_action)

        record_action = QAction("⏺  Iniciar Gravação", menu)
        record_action.triggered.connect(self._on_hotkey)
        menu.addAction(record_action)
        self._tray_record_action = record_action

        menu.addSeparator()

        quit_action = QAction("✕  Sair", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_settings()

    def _show_settings(self):
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _register_hotkey(self, hotkey):
        """Registra hotkey global."""
        # Para thread anterior
        if self._hotkey_thread and self._hotkey_thread.is_alive():
            try:
                import keyboard
                keyboard.unhook_all()
            except Exception:
                pass

        def hotkey_listener():
            try:
                import keyboard
                keyboard.add_hotkey(hotkey, self.hotkey_signal.triggered.emit)
                keyboard.wait()
            except Exception as e:
                print(f"Erro ao registrar hotkey: {e}")

        self._hotkey_thread = threading.Thread(target=hotkey_listener, daemon=True)
        self._hotkey_thread.start()

    def _on_hotkey(self):
        """Atalho pressionado — mostra seletor de monitor ou overlay."""
        if self.recorder.is_recording:
            # Se já está gravando, mostra/esconde overlay
            if self.overlay.isVisible():
                self.overlay.hide()
            else:
                pos = self.config.get("overlay_position", "bottom")
                self.overlay.show_at_position(pos)
        else:
            # Mostra seletor de monitor
            self.monitor_selector.show_centered()

    def _on_monitor_selected(self, monitor_indices):
        """Tela(s) selecionada(s) — inicia gravação.

        monitor_indices: lista de índices; [-1] significa todas as telas.
        """
        if isinstance(monitor_indices, int):
            monitor_indices = [monitor_indices]
        capture_all = (-1 in monitor_indices)
        idx = None if capture_all else monitor_indices

        error = self.recorder.start(monitor_indices=idx, capture_all=capture_all)
        if error:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Erro", f"Erro ao iniciar gravação:\n{error}")
            return

        # Mostra overlay
        pos = self.config.get("overlay_position", "bottom")
        self.overlay.set_recording_state(True)
        self.overlay.show_at_position(pos)

        # Atualiza tray
        self.tray_icon.setIcon(self._create_recording_icon())
        self.tray_icon.setToolTip("Screvo — Gravando...")
        self._tray_record_action.setText("⏹  Parar Gravação")

        # Timer
        self._time_timer.start()

    def _on_monitor_cancelled(self):
        pass

    def _on_region_requested(self):
        """Abre o seletor de região da tela."""
        self.region_selector.start()

    def _on_region_selected(self, region):
        """Região selecionada — inicia a gravação apenas dessa área."""
        error = self.recorder.start(region=region)
        if error:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Erro", f"Erro ao iniciar gravação:\n{error}")
            return

        pos = self.config.get("overlay_position", "bottom")
        self.overlay.set_recording_state(True)
        self.overlay.show_at_position(pos)

        self.tray_icon.setIcon(self._create_recording_icon())
        self.tray_icon.setToolTip("Screvo — Gravando...")
        self._tray_record_action.setText("⏹  Parar Gravação")
        self._time_timer.start()

    def _on_window_selected(self, hwnd):
        """Janela selecionada — grava via gdigrab window title."""
        # gdigrab suporta captura por título de janela
        import ctypes
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        window_title = buf.value

        error = self.recorder.start_window(window_title)
        if error:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Erro", f"Erro ao iniciar gravação:\n{error}")
            return

        pos = self.config.get("overlay_position", "bottom")
        self.overlay.set_recording_state(True)
        self.overlay.show_at_position(pos)

        self.tray_icon.setIcon(self._create_recording_icon())
        self.tray_icon.setToolTip("Screvo — Gravando...")
        self._tray_record_action.setText("⏹  Parar Gravação")
        self._time_timer.start()

    def _on_overlay_record(self):
        """Botão de gravar no overlay (quando não está gravando)."""
        if not self.recorder.is_recording:
            self.monitor_selector.show_centered()
            self.overlay.hide()

    def _on_overlay_pause(self):
        """Botão pause no overlay."""
        self.recorder.toggle_pause()
        self.overlay.set_recording_state(True, self.recorder.is_paused)

    def _on_overlay_marker(self):
        """Botão de marcador no overlay — registra o instante atual."""
        marker = self.recorder.add_marker()
        if marker:
            t = int(marker["time"])
            ts = f"{t // 60:02d}:{t % 60:02d}"
            self.tray_icon.showMessage(
                "Marcador adicionado",
                f"{marker['label']} em {ts}",
                QSystemTrayIcon.MessageIcon.Information, 1500
            )

    def _on_overlay_stop(self):
        """Para gravação — mostra 'Salvando...' enquanto FFmpeg finaliza."""
        self.overlay.set_saving_state(True)
        self._time_timer.stop()

        # Para em thread separada pra não travar UI.
        # Retorna à main thread via sinal Qt (queued connection) — NÃO usar
        # QTimer a partir de uma thread sem event loop (nunca dispara).
        def stop_worker():
            output = self.recorder.stop()
            self.stop_signal.done.emit(output)

        import threading
        threading.Thread(target=stop_worker, daemon=True).start()

    def _on_stop_complete(self, output):
        """Chamado quando FFmpeg terminou de salvar."""
        self.overlay.set_saving_state(False)
        self.overlay.set_recording_state(False)
        self.overlay.hide()

        # Restaura tray
        self.tray_icon.setIcon(self._create_tray_icon())
        self.tray_icon.setToolTip("Screvo")
        self._tray_record_action.setText("⏺  Iniciar Gravação")

        if output and os.path.isfile(output):
            self.tray_icon.showMessage(
                "Gravação Salva",
                f"Arquivo salvo em:\n{output}",
                QSystemTrayIcon.MessageIcon.Information,
                5000
            )

    def _on_overlay_close(self):
        """Fecha overlay (e para gravação se ativa)."""
        if self.recorder.is_recording:
            self._on_overlay_stop()
            # Não esconde aqui — _on_stop_complete vai esconder depois de salvar
        else:
            self.overlay.hide()

    def _update_overlay_time(self):
        """Atualiza timer do overlay."""
        if self.recorder.is_recording:
            self.overlay.update_time(self.recorder.get_elapsed_str())

    def _on_settings_changed(self):
        pass

    def _quit(self):
        if self.recorder.is_recording:
            self.recorder.stop()
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass
        self.tray_icon.hide()
        self.app.quit()

    def run(self):
        if not self.config.get("start_hidden", False):
            self._show_settings()
        return self.app.exec()
