"""
Tema visual inspirado no Handy — rosa, cards, toggles, sidebar gradiente.
"""

MAIN_STYLESHEET = """
/* ============== GLOBAL ============== */
QWidget {
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
    color: #333333;
}

/* ============== MAIN WINDOW ============== */
QMainWindow, #settingsWindow {
    background-color: #FAFAFA;
}

/* ============== SIDEBAR ============== */
#sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FFB6C1, stop:0.5 #FF91A4, stop:1 #FF69B4);
    min-width: 180px;
    max-width: 180px;
    border-top-left-radius: 12px;
    border-bottom-left-radius: 12px;
}

#appLogo {
    font-size: 32px;
    font-weight: 800;
    color: white;
    padding: 30px 20px 20px 20px;
    font-family: 'Segoe UI Black', 'Segoe UI', sans-serif;
}

/* Sidebar buttons */
QPushButton.sidebarBtn {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.85);
    text-align: left;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: 500;
    border-radius: 8px;
    margin: 2px 10px;
}

QPushButton.sidebarBtn:hover {
    background: rgba(255, 255, 255, 0.2);
    color: white;
}

QPushButton.sidebarBtn[active="true"] {
    background: rgba(255, 255, 255, 0.35);
    color: white;
    font-weight: 600;
}

/* ============== CONTENT AREA ============== */
#contentArea {
    background-color: #FAFAFA;
    border-top-right-radius: 12px;
    border-bottom-right-radius: 12px;
}

#contentStack {
    background: transparent;
}

/* ============== SECTION LABELS ============== */
QLabel.sectionTitle {
    font-size: 12px;
    font-weight: 700;
    color: #999999;
    letter-spacing: 1px;
    padding: 15px 0px 8px 0px;
}

/* ============== CARDS / SETTING ROWS ============== */
QFrame.settingCard {
    background-color: white;
    border: 1px solid #F0F0F0;
    border-radius: 10px;
    padding: 0px;
}

QFrame.settingRow {
    background: transparent;
    padding: 12px 16px;
    min-height: 44px;
}

QFrame.settingRow:hover {
    background-color: #FFF5F7;
}

/* Separator inside cards */
QFrame.separator {
    background-color: #F0F0F0;
    max-height: 1px;
    min-height: 1px;
}

/* ============== LABELS ============== */
QLabel.settingLabel {
    font-size: 13px;
    font-weight: 500;
    color: #333333;
}

QLabel.settingDescription {
    font-size: 11px;
    color: #AAAAAA;
}

QLabel.infoIcon {
    font-size: 12px;
    color: #CCCCCC;
}

/* ============== TOGGLE SWITCH (custom widget) ============== */

/* ============== COMBOBOX ============== */
QComboBox {
    background-color: #F5F5F5;
    border: 1px solid #E8E8E8;
    border-radius: 8px;
    padding: 8px 12px;
    min-width: 180px;
    font-size: 13px;
    color: #333333;
}

QComboBox:hover {
    border-color: #FFB6C1;
}

QComboBox:focus {
    border-color: #FF69B4;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #999999;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: white;
    border: 1px solid #FFE4E9;
    border-radius: 8px;
    selection-background-color: #FFE4E9;
    selection-color: #333333;
    color: #333333;
    outline: none;
    padding: 4px;
}

QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 10px;
    border-radius: 6px;
    color: #333333;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #FFF5F7;
    color: #333333;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #FFE4E9;
    color: #FF69B4;
}

/* ============== SLIDER ============== */
QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #F0F0F0;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #FF69B4;
    border: 2px solid white;
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 10px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #FF69B4, stop:1 #FF91A4);
    border-radius: 3px;
}

/* ============== LINE EDIT ============== */
QLineEdit {
    background-color: #F5F5F5;
    border: 1px solid #E8E8E8;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    color: #333333;
}

QLineEdit:focus {
    border-color: #FF69B4;
    background-color: white;
}

/* ============== PUSH BUTTON (general) ============== */
QPushButton {
    background-color: #F5F5F5;
    border: 1px solid #E8E8E8;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    color: #333333;
}

QPushButton:hover {
    background-color: #FFE4E9;
    border-color: #FFB6C1;
}

QPushButton:pressed {
    background-color: #FFB6C1;
}

/* Hotkey display button */
QPushButton.hotkeyBtn {
    background-color: #F5F5F5;
    border: 1px solid #E8E8E8;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    color: #333333;
    min-width: 120px;
}

/* Reset/refresh button */
QPushButton.resetBtn {
    background: transparent;
    border: 1px solid #E8E8E8;
    border-radius: 6px;
    padding: 6px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14px;
}

QPushButton.resetBtn:hover {
    background-color: #FFE4E9;
}

/* Browse button */
QPushButton.browseBtn {
    background-color: #FF69B4;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    color: white;
    font-weight: 600;
}

QPushButton.browseBtn:hover {
    background-color: #FF91A4;
}

/* ============== SCROLL AREA ============== */
QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #DDDDDD;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #FFB6C1;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

/* ============== TOOLTIP ============== */
QToolTip {
    background-color: #333333;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}

/* ============== SYSTEM TRAY MENU ============== */
QMenu {
    background-color: white;
    border: 1px solid #E8E8E8;
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 8px 20px;
    border-radius: 6px;
}

QMenu::item:selected {
    background-color: #FFE4E9;
}
"""

OVERLAY_STYLESHEET = """
#overlayWidget {
    background-color: rgba(30, 30, 30, 230);
    border-radius: 25px;
    border: 2px solid rgba(255, 105, 180, 0.6);
}

QPushButton.overlayBtn {
    background: transparent;
    border: 2px solid rgba(255, 105, 180, 0.5);
    border-radius: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    color: #FF69B4;
    font-size: 16px;
    font-weight: bold;
}

QPushButton.overlayBtn:hover {
    background: rgba(255, 105, 180, 0.2);
    border-color: #FF69B4;
}

QPushButton.overlayBtn[recording="true"] {
    border-color: #FF1744;
    color: #FF1744;
}

QPushButton.overlayCloseBtn {
    background: transparent;
    border: 2px solid rgba(255, 80, 80, 0.5);
    border-radius: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    color: #FF5050;
    font-size: 16px;
    font-weight: bold;
}

QPushButton.overlayCloseBtn:hover {
    background: rgba(255, 80, 80, 0.3);
    border-color: #FF5050;
}

QLabel.overlayTimer {
    color: rgba(255, 255, 255, 0.7);
    font-size: 13px;
    font-weight: 600;
    font-family: 'Consolas', 'Courier New', monospace;
}

QLabel.overlayDot {
    color: rgba(255, 105, 180, 0.4);
    font-size: 20px;
}

QLabel.overlayDotActive {
    color: #FF69B4;
    font-size: 20px;
}
"""

MONITOR_SELECTOR_STYLESHEET = """
#monitorSelector {
    background-color: rgba(20, 20, 20, 240);
    border-radius: 16px;
    border: 2px solid rgba(255, 105, 180, 0.4);
}

QLabel.monitorTitle {
    color: white;
    font-size: 16px;
    font-weight: 600;
}

QLabel.monitorSubtitle {
    color: rgba(255, 255, 255, 0.6);
    font-size: 12px;
}

QPushButton.monitorBtn {
    background: rgba(255, 255, 255, 0.05);
    border: 2px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    padding: 12px;
    color: white;
    font-size: 13px;
}

QPushButton.monitorBtn:hover {
    background: rgba(255, 105, 180, 0.15);
    border-color: rgba(255, 105, 180, 0.5);
}

QPushButton.monitorBtn:checked {
    background: rgba(255, 105, 180, 0.2);
    border-color: #FF69B4;
}

QPushButton.monitorStartBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #FF69B4, stop:1 #FF91A4);
    border: none;
    border-radius: 10px;
    padding: 12px 32px;
    color: white;
    font-size: 14px;
    font-weight: 600;
}

QPushButton.monitorStartBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #FF91A4, stop:1 #FFB6C1);
}

QPushButton.monitorCancelBtn {
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 10px;
    padding: 12px 32px;
    color: rgba(255, 255, 255, 0.7);
    font-size: 14px;
}

QPushButton.monitorCancelBtn:hover {
    background: rgba(255, 255, 255, 0.1);
}
"""
