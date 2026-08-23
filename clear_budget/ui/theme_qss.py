"""Application stylesheet builder, parameterised by theme tokens.

`build_qss(tokens)` renders the whole app stylesheet from a theme_tokens
dict, so dark and light are the same template with different tokens. The
theme manager (theme.py) chooses the tokens and applies the result to the
QApplication.
"""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase

from clear_budget.ui import ui_scale
from clear_budget.ui._theme_controls import control_qss, widget_extras_qss
from clear_budget.ui._theme_inputs import combo_qss, input_qss
from clear_budget.ui._theme_menus import menu_qss
from clear_budget.ui._theme_tabs import TAB_BAR_LEFT_INSET_PX, tab_qss

SCROLLBAR_WIDTH_PX = 8

# TAB_BAR_LEFT_INSET_PX is re-exported from _theme_tabs, where it sits beside
# the rule that uses it. The pill geometry that used to be re-exported here
# (margins, border width, corner radius) went with NavTabBar: it existed so the
# cursor ring could be painted on exactly the pill the stylesheet drew; there
# is no longer a pill or a cursor.
__all__ = [
    "SCROLLBAR_WIDTH_PX",
    "TAB_BAR_LEFT_INSET_PX",
    "build_qss",
]

# Generic CSS family used as a final backstop if the platform reports no
# resolvable UI font name.
_FALLBACK_FONT_FAMILY = "sans-serif"


def _ui_font_family() -> str:
    """Return the native UI font family for the current platform.

    Uses Qt's resolved system UI font so the app matches each desktop instead
    of hardcoding a Windows-only face: Segoe UI on Windows, the San Francisco
    system font on macOS and the desktop default (e.g. Ubuntu, Noto Sans,
    DejaVu Sans) on Debian/Ubuntu Linux.  Requires a running QApplication,
    which the composition root creates before applying this stylesheet.
    """
    family = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
    return family or _FALLBACK_FONT_FAMILY


def build_qss(t: dict[str, str], s: dict[str, str]) -> str:
    """Render the whole app stylesheet from chrome tokens `t` and states `s`."""
    base_pt = round(14 * ui_scale.factor())
    font_family = _ui_font_family()
    return f"""
QWidget {{
    background-color: {t["window_bg"]};
    color: {t["text"]};
    font-family: '{font_family}', {_FALLBACK_FONT_FAMILY};
    font-size: {base_pt}pt;
    /* The green ring border is the one focus indicator; stop the native
       style drawing its own dotted rectangle around a control's text. */
    outline: none;
}}

QMainWindow {{
    background-color: {t["window_bg"]};
}}

{tab_qss(t)}
QGroupBox {{
    border: 1px solid {t["border"]};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    color: {t["accent"]};
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}}

QTableWidget {{
    background-color: {t["panel_bg"]};
    gridline-color: {t["border"]};
    color: {t["text"]};
    selection-background-color: {t["selection_bg"]};
    selection-color: {t["text"]};
    border: 2px solid transparent;
}}

QTableWidget:enabled:focus {{
    border: 2px solid {t["ring"]};
}}

QHeaderView::section {{
    background-color: {t["window_bg"]};
    color: {t["text_muted"]};
    border: 1px solid {t["border"]};
    padding: 4px;
}}

QTableWidget::item:selected {{
    background-color: {t["selection_bg"]};
}}

QPushButton {{
    background-color: {t["primary_bg"]};
    color: {t["primary_text"]};
    border: 2px solid transparent;
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: 600;
}}

QPushButton:enabled:hover {{
    background-color: {t["primary_hover"]};
    border: 2px solid {t["ring"]};
}}

QPushButton:enabled:focus {{
    border: 2px solid {t["ring"]};
}}

QPushButton:pressed {{
    background-color: {t["primary_pressed"]};
    border: 2px solid {t["ring"]};
}}

QPushButton:disabled {{
    background-color: {t["disabled_fill"]};
    color: {t["text_disabled"]};
    border: 2px solid {t["danger"]};
}}

QPushButton#DangerButton {{
    background-color: {t["danger_btn_bg"]};
}}

QPushButton#DangerButton:enabled:hover {{
    background-color: {t["danger_btn_hover"]};
    border: 2px solid {t["ring"]};
}}

QPushButton#DangerButton:enabled:focus {{
    border: 2px solid {t["ring"]};
}}

QPushButton#DangerButton:disabled {{
    background-color: {t["disabled_fill"]};
    border: 2px solid {t["danger"]};
}}

QLabel {{
    color: {t["text"]};
}}

QLabel#SolvencyGood {{
    color: {t["ring"]};
    font-weight: bold;
}}

QLabel#SolvencyBad {{
    color: {t["danger"]};
    font-weight: bold;
}}

QLabel#SolvencyWarn {{
    color: {t["warn"]};
    font-weight: bold;
}}

{input_qss(t)}
{control_qss(t)}
{widget_extras_qss(t, s)}
{combo_qss(t)}

QProgressBar {{
    background-color: {t["inset_bg"]};
    border: 1px solid {t["border"]};
    border-radius: 5px;
    height: 14px;
}}

QProgressBar::chunk {{
    background-color: {t["accent"]};
    border-radius: 4px;
}}

QScrollBar:vertical {{
    background-color: {t["panel_bg"]};
    width: {SCROLLBAR_WIDTH_PX}px;
}}

QScrollBar::handle:vertical {{
    background-color: {t["scroll_handle"]};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {t["scroll_handle_hover"]};
}}

QStatusBar {{
    background-color: {t["inset_bg"]};
    color: {t["text_muted"]};
    border-top: 1px solid {t["border"]};
}}

QDialog {{
    background-color: {t["window_bg"]};
}}

QMessageBox {{
    background-color: {t["window_bg"]};
}}

QCheckBox {{
    spacing: 8px;
    color: {t["text"]};
}}

QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 2px solid {t["text_muted"]};
    border-radius: 3px;
    background: transparent;
}}

QCheckBox::indicator:checked {{
    background: {t["ring"]};
    border-color: {t["ring"]};
}}

QCheckBox::indicator:unchecked:hover {{
    border-color: {t["checkbox_hover"]};
}}

QCheckBox::indicator:disabled {{
    border-color: {t["danger"]};
    background: transparent;
}}

QCheckBox:enabled:focus {{
    color: {t["accent"]};
}}

{menu_qss(t)}"""
