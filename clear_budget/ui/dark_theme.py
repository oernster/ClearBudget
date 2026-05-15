"""Dark theme QSS stylesheet for ClearBudget."""

DARK_QSS = """
/* Main Window */
QWidget {
    background-color: #161827;
    color: #e5e7eb;
    font-family: 'Segoe UI', sans-serif;
    font-size: 11px;
}

QMainWindow {
    background-color: #161827;
}

/* Menu Bar */
QMenuBar {
    background-color: #161827;
    color: #e5e7eb;
    border-bottom: 1px solid #2b2f44;
}

QMenuBar::item:selected {
    background-color: #1e2130;
}

QMenu {
    background-color: #1e2130;
    color: #e5e7eb;
    border: 1px solid #2b2f44;
}

QMenu::item:selected {
    background-color: #312e81;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #2b2f44;
    background-color: #1e2130;
}

QTabBar::tab {
    background-color: #1e2130;
    color: #9ca3af;
    padding: 8px 16px;
    border: 1px solid #2b2f44;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #161827;
    color: #a78bfa;
    border-bottom: 2px solid #a78bfa;
    padding-bottom: 6px;
}

QTabBar::tab:hover {
    background-color: #1e2130;
    color: #cbd5e1;
}

/* GroupBox */
QGroupBox {
    border: 1px solid #2b2f44;
    border-radius: 6px;
    margin-top: 12px;
    color: #a78bfa;
    font-weight: 600;
    padding-top: 12px;
    padding-left: 8px;
    padding-right: 8px;
    padding-bottom: 8px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}

/* Table */
QTableWidget {
    background-color: #1e2130;
    gridline-color: #2b2f44;
    color: #e5e7eb;
    selection-background-color: #312e81;
    border: 1px solid #2b2f44;
}

QHeaderView::section {
    background-color: #161827;
    color: #9ca3af;
    border: 1px solid #2b2f44;
    padding: 4px;
    font-weight: 600;
}

QTableWidget::item:selected {
    background-color: #312e81;
    color: #e5e7eb;
}

/* Button */
QPushButton {
    background-color: #7fb0ff;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 11px;
}

QPushButton:hover {
    background-color: #6aa2ff;
}

QPushButton:pressed {
    background-color: #5a92ff;
}

QPushButton:disabled {
    background-color: #4b7aa8;
    color: #999999;
}

QPushButton#DangerButton {
    background-color: #7a1f25;
}

QPushButton#DangerButton:hover {
    background-color: #6a1b21;
}

/* LineEdit */
QLineEdit {
    background-color: #0f1220;
    color: #e5e7eb;
    border: 1px solid #2b2f44;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #312e81;
}

QLineEdit:focus {
    border: 1px solid #a78bfa;
}

/* Label */
QLabel {
    color: #e5e7eb;
}

QLabel#SolvencyGood {
    color: #34d399;
    font-weight: bold;
}

QLabel#SolvencyBad {
    color: #f87171;
    font-weight: bold;
}

QLabel#SolvencyWarn {
    color: #fbbf24;
    font-weight: bold;
}

/* ProgressBar */
QProgressBar {
    background-color: #0f1220;
    border: 1px solid #2b2f44;
    border-radius: 6px;
    height: 16px;
    text-align: center;
    color: #cbd5e1;
}

QProgressBar::chunk {
    background-color: #a78bfa;
    border-radius: 4px;
    width: 10px;
    margin: 1px;
}

/* ScrollBar */
QScrollBar:vertical {
    background-color: #1e2130;
    width: 12px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #2b2f44;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #3a3f54;
}

QScrollBar:horizontal {
    background-color: #1e2130;
    height: 12px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #2b2f44;
    border-radius: 6px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #3a3f54;
}

QScrollBar::add-line, QScrollBar::sub-line {
    border: none;
    background: none;
}

/* Checkbox */
QCheckBox {
    color: #e5e7eb;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #2b2f44;
    border-radius: 3px;
    background-color: #0f1220;
}

QCheckBox::indicator:checked {
    background-color: #a78bfa;
    border: 1px solid #a78bfa;
}

/* Dialog */
QDialog {
    background-color: #161827;
}
"""
