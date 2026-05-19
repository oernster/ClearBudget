"""Dark theme stylesheet for ClearBudget UI."""

from __future__ import annotations

from clear_budget.ui import ui_scale


def get_dark_qss() -> str:
    base_pt = round(14 * ui_scale.factor())
    return f"""
QWidget {{
    background-color: #161827;
    color: #e5e7eb;
    font-family: 'Segoe UI';
    font-size: {base_pt}pt;
}}

QMainWindow {{
    background-color: #161827;
}}

QTabWidget::pane {{
    border: 1px solid #2b2f44;
    background-color: #1e2130;
}}

QTabBar::tab {{
    background-color: #1e2130;
    color: #9ca3af;
    padding: 8px 16px;
    border: 2px solid #2b2f44;
    border-bottom: none;
}}

QTabBar::tab:selected {{
    background-color: #161827;
    color: #a78bfa;
    border: 2px solid #a78bfa;
    border-bottom: none;
}}

QTabBar::tab:hover:!selected {{
    background-color: #2b2f44;
    border: 2px solid #f59e0b;
    color: #f59e0b;
}}

QGroupBox {{
    border: 1px solid #2b2f44;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    color: #a78bfa;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}}

QTableWidget {{
    background-color: #1e2130;
    gridline-color: #2b2f44;
    color: #e5e7eb;
    selection-background-color: #312e81;
}}

QHeaderView::section {{
    background-color: #161827;
    color: #9ca3af;
    border: 1px solid #2b2f44;
    padding: 4px;
}}

QTableWidget::item:selected {{
    background-color: #312e81;
}}

QPushButton {{
    background-color: #7fb0ff;
    color: white;
    border: 2px solid transparent;
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: #6aa2ff;
    border: 2px solid #f59e0b;
}}

QPushButton:pressed {{
    background-color: #5a92ff;
    border: 2px solid #f59e0b;
}}

QPushButton#DangerButton {{
    background-color: #7a1f25;
}}

QPushButton#DangerButton:hover {{
    background-color: #6a1b21;
}}

QLabel {{
    color: #e5e7eb;
}}

QLabel#SolvencyGood {{
    color: #34d399;
    font-weight: bold;
}}

QLabel#SolvencyBad {{
    color: #f87171;
    font-weight: bold;
}}

QLabel#SolvencyWarn {{
    color: #fbbf24;
    font-weight: bold;
}}

QLineEdit {{
    background-color: #1e2130;
    color: #e5e7eb;
    border: 1px solid #2b2f44;
    border-radius: 4px;
    padding: 4px 8px;
}}

QLineEdit:focus {{
    border: 2px solid #a78bfa;
}}

QSpinBox, QDoubleSpinBox {{
    background-color: #1e2130;
    color: #e5e7eb;
    border: 1px solid #2b2f44;
    border-radius: 4px;
    padding: 4px 8px;
}}

QComboBox {{
    background-color: #1e2130;
    color: #e5e7eb;
    border: 1px solid #2b2f44;
    border-radius: 4px;
    padding: 4px 8px;
}}

QComboBox::drop-down {{
    border: none;
}}

QProgressBar {{
    background-color: #0f1220;
    border: 1px solid #2b2f44;
    border-radius: 5px;
    height: 14px;
}}

QProgressBar::chunk {{
    background-color: #a78bfa;
    border-radius: 4px;
}}

QScrollBar:vertical {{
    background-color: #1e2130;
    width: 8px;
}}

QScrollBar::handle:vertical {{
    background-color: #2b2f44;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #3b3f54;
}}

QStatusBar {{
    background-color: #0f1220;
    color: #9ca3af;
    border-top: 1px solid #2b2f44;
}}

QDialog {{
    background-color: #161827;
}}

QMessageBox {{
    background-color: #161827;
}}

QCheckBox {{
    spacing: 8px;
    color: #e5e7eb;
}}

QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 2px solid #9ca3af;
    border-radius: 3px;
    background: transparent;
}}

QCheckBox::indicator:checked {{
    background: #34d399;
    border-color: #34d399;
}}

QCheckBox::indicator:unchecked:hover {{
    border-color: #d1d5db;
}}

QMenuBar {{
    background-color: #161827;
    color: #e5e7eb;
    border-bottom: 1px solid #2b2f44;
}}

QMenuBar::item {{
    background: transparent;
    padding: 4px 12px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    border: 2px solid #f59e0b;
    border-radius: 4px;
    color: #f59e0b;
}}

QMenuBar::item:pressed {{
    background-color: #2b2f44;
    border: 2px solid #f59e0b;
    border-radius: 4px;
}}

QMenu {{
    background-color: #1e2130;
    color: #e5e7eb;
    border: 1px solid #2b2f44;
    border-radius: 4px;
    padding: 4px 0px;
}}

QMenu::item {{
    padding: 6px 24px 6px 12px;
    border: 2px solid transparent;
    border-radius: 3px;
    margin: 2px 4px;
}}

QMenu::item:selected {{
    border: 2px solid #f59e0b;
    color: #f59e0b;
    background-color: transparent;
}}

QMenu::separator {{
    height: 1px;
    background-color: #2b2f44;
    margin: 4px 8px;
}}
"""
