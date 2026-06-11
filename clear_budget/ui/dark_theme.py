"""Dark theme stylesheet for ClearBudget UI."""

from __future__ import annotations

from clear_budget.ui import ui_scale

SCROLLBAR_WIDTH_PX = 8


def get_dark_qss() -> str:
    base_pt = round(14 * ui_scale.factor())
    return f"""
QWidget {{
    background-color: #0a0a0d;
    color: #e5e7eb;
    font-family: 'Segoe UI';
    font-size: {base_pt}pt;
}}

QMainWindow {{
    background-color: #0a0a0d;
}}

QTabWidget::pane {{
    border: 1px solid #3a4156;
    background-color: #242938;
}}

QTabBar::tab {{
    background-color: #242938;
    color: #9ca3af;
    padding: 8px 16px;
    border: 2px solid #3a4156;
    border-bottom: none;
}}

QTabBar::tab:selected {{
    background-color: #0a0a0d;
    color: #2dd4bf;
    border: 2px solid #2dd4bf;
    border-bottom: none;
}}

QTabBar::tab:hover:!selected {{
    background-color: #3a4156;
    border: 2px solid #34d399;
    color: #34d399;
}}

QGroupBox {{
    border: 1px solid #3a4156;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    color: #2dd4bf;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}}

QTableWidget {{
    background-color: #242938;
    gridline-color: #3a4156;
    color: #e5e7eb;
    selection-background-color: #1e3a5f;
}}

QHeaderView::section {{
    background-color: #0a0a0d;
    color: #9ca3af;
    border: 1px solid #3a4156;
    padding: 4px;
}}

QTableWidget::item:selected {{
    background-color: #1e3a5f;
}}

QPushButton {{
    background-color: #3b5bdb;
    color: white;
    border: 2px solid transparent;
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: #4a68d6;
    border: 2px solid #34d399;
}}

QPushButton:pressed {{
    background-color: #2f4bb8;
    border: 2px solid #34d399;
}}

QPushButton:disabled {{
    background-color: #3a4156;
    color: #6b7280;
    border: 2px solid #f87171;
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
    background-color: #242938;
    color: #e5e7eb;
    border: 1px solid #3a4156;
    border-radius: 4px;
    padding: 4px 8px;
}}

QLineEdit:focus {{
    border: 2px solid #2dd4bf;
}}

QLineEdit:disabled {{
    border: 2px solid #f87171;
    color: #6b7280;
}}

QSpinBox, QDoubleSpinBox {{
    background-color: #242938;
    color: #e5e7eb;
    border: 1px solid #3a4156;
    border-radius: 4px;
    padding: 4px 8px;
}}

QSpinBox:disabled, QDoubleSpinBox:disabled {{
    border: 2px solid #f87171;
    color: #6b7280;
}}

QComboBox {{
    background-color: #242938;
    color: #e5e7eb;
    border: 1px solid #3a4156;
    border-radius: 4px;
    padding: 4px 8px;
}}

QComboBox:disabled {{
    border: 2px solid #f87171;
    color: #6b7280;
}}

QComboBox::drop-down {{
    border: none;
}}

QProgressBar {{
    background-color: #06070c;
    border: 1px solid #3a4156;
    border-radius: 5px;
    height: 14px;
}}

QProgressBar::chunk {{
    background-color: #2dd4bf;
    border-radius: 4px;
}}

QScrollBar:vertical {{
    background-color: #242938;
    width: 8px;
}}

QScrollBar::handle:vertical {{
    background-color: #9aa3c2;
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #c4cae0;
}}

QStatusBar {{
    background-color: #06070c;
    color: #9ca3af;
    border-top: 1px solid #3a4156;
}}

QDialog {{
    background-color: #0a0a0d;
}}

QMessageBox {{
    background-color: #0a0a0d;
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

QCheckBox::indicator:disabled {{
    border-color: #f87171;
    background: transparent;
}}

QMenuBar {{
    background-color: #0a0a0d;
    color: #e5e7eb;
    border-bottom: 1px solid #3a4156;
}}

QMenuBar::item {{
    background: transparent;
    padding: 4px 12px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    border: 2px solid #34d399;
    border-radius: 4px;
    color: #34d399;
}}

QMenuBar::item:pressed {{
    background-color: #3a4156;
    border: 2px solid #34d399;
    border-radius: 4px;
}}

QMenu {{
    background-color: #242938;
    color: #e5e7eb;
    border: 1px solid #3a4156;
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
    border: 2px solid #34d399;
    color: #34d399;
    background-color: transparent;
}}

QMenu::separator {{
    height: 1px;
    background-color: #3a4156;
    margin: 4px 8px;
}}
"""
