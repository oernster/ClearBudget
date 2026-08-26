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
from clear_budget.ui._theme_pane import TAB_BAR_LEFT_INSET_PX, pane_qss
from clear_budget.ui.theme_tokens import STATE_SAFE

SCROLLBAR_WIDTH_PX = 8

# TAB_BAR_LEFT_INSET_PX is re-exported from _theme_pane, where it sits beside
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


# Vertical chrome inside a table. These live here rather than inline in the
# stylesheet because `utils.text_metrics` has to agree with them EXACTLY: a row
# is only tall enough if it clears whichever of the two is larger. They were
# the bug. A header section spends padding plus a border top and bottom, so a
# row pinned at 28px left 18px for a line box needing 26px and the descender
# was simply cut: "Aug" rendered as "Auq".
HEADER_SECTION_PADDING_PX = 4
HEADER_SECTION_BORDER_PX = 1
# Breathing room above and below a cell's text. There was NO item rule at all,
# so a cell was its font's line box with nothing spare.
TABLE_ITEM_VPADDING_PX = 4
# Comfort margin ON TOP of the exact line box. Fitting the descender exactly is
# correct but sits on the bound, so a row reads cramped and any rounding at a
# different display scale puts it back on the baseline. This is the deliberate
# space, distinct from the chrome above, which is the arithmetic.
TEXT_BREATHING_PX = 4


def _card_toggle_qss(t: dict[str, str]) -> str:
    """The card Active toggle as a pill-and-knob slider (see switch_images).

    Lives here rather than in the per-surface builders because generating the
    images needs a QApplication, which the pure string builders must not: the
    highlight rule is testable Qt-free precisely because they touch no Qt.
    The ring stays the widget's own border (hover/focus green, disabled red,
    the three-state model), because a widget-state-then-subcontrol selector
    (`QCheckBox:focus::indicator`) is parsed and then silently ignored.
    """
    from clear_budget.ui.switch_images import switch_size, switch_url

    width, height = switch_size()
    on_url = switch_url(track=t["checked_fill"], knob=t["primary_text"], on=True)
    off_url = switch_url(track=t["border"], knob=t["primary_text"], on=False)
    on_off_urls_disabled = (
        switch_url(track=t["border"], knob=t["text_disabled"], on=True),
        switch_url(track=t["border"], knob=t["text_disabled"], on=False),
    )
    ring_radius = height // 2 + 2
    return f"""
QCheckBox#CardActiveToggle {{
    border: 2px solid transparent;
    border-radius: {ring_radius}px;
    /* The card panel must show through. Without this the blanket
       `QWidget` background paints the whole checkbox rect in the window
       colour, which is darker than the panel it sits on, while the pill is
       narrower than that rect: a checkbox with no text still reserves its
       spacing, so a dark block sat to the right of the switch. */
    background: transparent;
    /* No text on this one, so the reserved gap is dead space that only ever
       widened the ring away from the pill. */
    spacing: 0px;
}}

QCheckBox#CardActiveToggle:enabled:hover {{
    border-color: {t["ring"]};
}}

QCheckBox#CardActiveToggle:enabled:focus {{
    border-color: {t["ring"]};
}}

QCheckBox#CardActiveToggle:disabled {{
    border-color: {t["danger"]};
}}

QCheckBox#CardActiveToggle::indicator {{
    width: {width}px;
    height: {height}px;
    border: none;
    border-radius: {height // 2}px;
    background: transparent;
}}

QCheckBox#CardActiveToggle::indicator:checked {{
    image: url({on_url});
    background: transparent;
}}

QCheckBox#CardActiveToggle::indicator:unchecked {{
    image: url({off_url});
    background: transparent;
}}

QCheckBox#CardActiveToggle::indicator:unchecked:hover {{
    border: none;
}}

QCheckBox#CardActiveToggle::indicator:checked:disabled {{
    image: url({on_off_urls_disabled[0]});
}}

QCheckBox#CardActiveToggle::indicator:unchecked:disabled {{
    image: url({on_off_urls_disabled[1]});
}}
"""


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

{pane_qss(t)}
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

/* A table draws NO ring, in any state. Its current row already says where
   the keyboard is: focusing one paints that row with no stylesheet rule at
   all. A rectangle round the whole pane adds nothing on top of that; it
   is also the wrong shape of feedback for a region the pointer sits inside. The
   transparent border above stays, so the geometry does not shift and the
   toolkit's own sunken frame stays suppressed. */

QHeaderView::section {{
    background-color: {t["window_bg"]};
    color: {t["text_muted"]};
    border: {HEADER_SECTION_BORDER_PX}px solid {t["border"]};
    padding: {HEADER_SECTION_PADDING_PX}px;
}}

QTableWidget::item {{
    padding-top: {TABLE_ITEM_VPADDING_PX}px;
    padding-bottom: {TABLE_ITEM_VPADDING_PX}px;
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
    color: {s[STATE_SAFE]};
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

/* The Recommendations page's try-it-on panel: an inset tray under a ticked
   suggestion carrying that change's measured effect. Inset colours so it
   reads as an annotation on the row above, never as new page copy. */
QWidget#TrialPanel {{
    background-color: {t["inset_bg"]};
    border: 1px solid {t["border"]};
    border-radius: 5px;
}}

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
    background: {t["checked_fill"]};
    border-color: {t["checked_fill"]};
}}

QCheckBox::indicator:unchecked:hover {{
    border-color: {t["checkbox_hover"]};
}}

QCheckBox::indicator:disabled {{
    border-color: {t["danger"]};
    background: transparent;
}}

/* The day-cannot-move flag (bill and income dialogs). Its TICK is a warning
   rather than a setting, so it fills red instead of the ordinary checked
   blue. Object-name scoped: id specificity beats the generic rule above. */
QCheckBox#DayFixedCheck::indicator:checked {{
    background: {t["danger_check_fill"]};
    border-color: {t["danger_check_fill"]};
}}

QCheckBox:enabled:focus {{
    color: {t["accent"]};
}}

{_card_toggle_qss(t)}
{menu_qss(t)}"""
