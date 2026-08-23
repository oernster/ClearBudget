"""Control and widget-extra sub-styling, parameterised by theme tokens.

Split from theme_qss to keep each module under the 400-LOC limit.
`control_qss` styles spin buttons, the date edit and the calendar popup;
`widget_extras_qss` carries the object-name rules for app-specific widgets
(nav tray, nav graph button, theme toggle, status-bar date label) so those
widgets need no inline colour styles of their own and appends the semantic
label roles from `_theme_labels`.
"""

from __future__ import annotations

from clear_budget.ui import ui_scale
from clear_budget.ui._theme_labels import label_roles_qss
from clear_budget.ui.spin_arrows import arrow_size, arrow_url

# Corner radius shared by the nav tray and the group boxes it matches.
_NAV_TRAY_RADIUS_PX = 6
# Spin-box button box. Wide and tall enough that the arrow SpinArrowStyle draws
# inside it reads clearly rather than being squeezed into a sliver; the two
# buttons split the field's height between them, so the minimum applies per
# button and sets the field's own height in practice.
SPIN_BUTTON_WIDTH_PX = 22
SPIN_BUTTON_MIN_HEIGHT_PX = 14
# Unscaled font size of the status-bar date label. The theme toggle's glyph is
# NOT sized here: it derives from the nav icon's height in code so the two read
# as a matched pair (see format_helpers._build_theme_toggle_button).
_STATUS_LABEL_FONT_PX = 18
# Tooltips read as secondary text, so a notch below the body size.
_TOOLTIP_FONT_PX = 12


def control_qss(t: dict[str, str]) -> str:
    """QSS for spin-box buttons, the date edit and the calendar popup."""
    arrow_w, arrow_h = arrow_size()
    up_arrow = arrow_url(t["text"], up=True)
    down_arrow = arrow_url(t["text"], up=False)
    up_arrow_disabled = arrow_url(t["text_disabled"], up=True)
    down_arrow_disabled = arrow_url(t["text_disabled"], up=False)
    return f"""
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: {SPIN_BUTTON_WIDTH_PX}px;
    min-height: {SPIN_BUTTON_MIN_HEIGHT_PX}px;
    border-left: 1px solid {t["border"]};
    border-top-right-radius: 4px;
    background-color: {t["panel_alt_bg"]};
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: {SPIN_BUTTON_WIDTH_PX}px;
    min-height: {SPIN_BUTTON_MIN_HEIGHT_PX}px;
    border-left: 1px solid {t["border"]};
    border-bottom-right-radius: 4px;
    background-color: {t["panel_alt_bg"]};
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {t["border"]};
}}

/* The arrows are images, not CSS triangles. Qt's stylesheet engine does not
   implement the `width: 0` plus transparent-border triangle idiom: it honours
   the zero size, draws nothing and leaves the button box behind, which is
   what showed two empty rectangles. image: url() is Qt's only stylesheet route
   to a glyph here; spin_arrows draws and caches one per colour. */
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({up_arrow});
    width: {arrow_w}px;
    height: {arrow_h}px;
}}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({down_arrow});
    width: {arrow_w}px;
    height: {arrow_h}px;
}}

QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled {{
    image: url({up_arrow_disabled});
}}

QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {{
    image: url({down_arrow_disabled});
}}

QDateEdit {{
    background-color: {t["panel_bg"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 4px;
    padding: 4px 8px;
}}

QDateEdit::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 24px;
    border-left: 1px solid {t["border"]};
}}

QDateEdit::down-arrow {{
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {t["text"]};
}}

QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background-color: {t["calendar_nav_bg"]};
}}

QCalendarWidget QToolButton {{
    color: {t["text"]};
    background-color: transparent;
    padding: 4px 8px;
}}

QCalendarWidget QToolButton:hover {{
    background-color: {t["border"]};
    border-radius: 4px;
}}

QCalendarWidget QMenu {{
    background-color: {t["panel_bg"]};
    color: {t["text"]};
}}

QCalendarWidget QSpinBox {{
    background-color: {t["panel_bg"]};
    color: {t["text"]};
}}

QCalendarWidget QAbstractItemView {{
    background-color: {t["panel_bg"]};
    color: {t["text"]};
    selection-background-color: {t["accent"]};
    selection-color: {t["calendar_sel_text"]};
    outline: none;
}}

QCalendarWidget QAbstractItemView:disabled {{
    color: {t["text_disabled"]};
}}
"""


def widget_extras_qss(t: dict[str, str], s: dict[str, str]) -> str:
    """Object-name rules for app widgets, so they carry no inline colours.

    Object-name selectors beat the generic rules by id specificity, so each
    of these buttons needs its OWN three-state ring rules (no ring at rest,
    green on hover/focus while enabled, permanent red while disabled).
    """
    status_px = ui_scale.px(_STATUS_LABEL_FONT_PX)
    tooltip_px = ui_scale.px(_TOOLTIP_FONT_PX)
    return f"""
#navTray {{
    border: 1px solid {t["border"]};
    border-radius: {_NAV_TRAY_RADIUS_PX}px;
}}

QPushButton#NavGraphButton, QPushButton#ThemeToggleButton {{
    background: transparent;
    border: 2px solid transparent;
    border-radius: 6px;
    padding: 2px;
}}

/* No font-size on the toggle on purpose: a stylesheet rule beats setFont and
   the toggle's glyph is sized in code from the nav icon's height so the two
   match. See _build_theme_toggle_button, which also fixes its square size. */

QPushButton#NavGraphButton:enabled:hover,
QPushButton#NavGraphButton:enabled:focus,
QPushButton#ThemeToggleButton:enabled:hover,
QPushButton#ThemeToggleButton:enabled:focus {{
    border: 2px solid {t["ring"]};
}}

QPushButton#NavGraphButton:disabled,
QPushButton#ThemeToggleButton:disabled {{
    border: 2px solid {t["danger"]};
}}

/* The four primary tabs, which are buttons in the navigation tray rather than
   a QTabBar. Same three-state ring as every other tray control, plus one
   extra state a plain button does not have: the tab being SHOWN carries the
   accent border, exactly as the selected pill did when these were a strip.
   The accent is a selection colour and never a ring, so the green still means
   only "the pointer or the keyboard is here".

   Marked through a dynamic property rather than an inline stylesheet, so a
   live theme switch repaints it (see tab_icons.mark_current_tab, which
   repolishes). The property selector needs the value quoted; Qt matches it as
   a string, so an unquoted true silently never matches. */
QPushButton#NavTabButton {{
    background: transparent;
    border: 2px solid transparent;
    border-radius: 6px;
    padding: 2px;
}}

/* The current tab is marked by a FILL and an accent UNDERLINE, never a full
   rectangle: rectangles are the ring vocabulary (green hover/focus, red
   disabled) and at 2px the accent teal is indistinguishable from the ring
   green, so on launch the current tab read as though it were hover-focused.
   Only the bottom border colour changes, so nothing reflows. */
QPushButton#NavTabButton[currentTab="true"] {{
    background-color: {t["panel_bg"]};
    border-bottom-color: {t["accent"]};
}}

QPushButton#NavTabButton:enabled:hover,
QPushButton#NavTabButton:enabled:focus {{
    border: 2px solid {t["ring"]};
}}

QPushButton#NavTabButton:disabled {{
    border: 2px solid {t["danger"]};
}}

/* The page body is a ring stop when it overflows, so it needs the same green
   ring every other stop shows; without one the keyboard would be on it with
   nothing to say so. Only :focus, never :hover: the pointer is over this
   surface most of the time the app is open and a ring following the mouse
   around the page would be noise rather than a signal. */
QScrollArea#TabScrollArea {{
    border: 2px solid transparent;
    border-radius: 6px;
}}

QScrollArea#TabScrollArea:enabled:focus {{
    border: 2px solid {t["ring"]};
}}

/* Tooltips were unstyled, so they took the platform default and (worse) any
   font-size a widget's own stylesheet happened to set (the theme toggle's
   emoji size leaked into its hover text). Sizing and theming them here gives
   every tooltip in the app one appearance. */
QToolTip {{
    font-size: {tooltip_px}px;
    color: {t["text"]};
    background-color: {t["panel_bg"]};
    border: 1px solid {t["border"]};
    padding: 4px 6px;
}}

QLabel#StatusDateLabel {{
    font-size: {status_px}px;
    font-weight: bold;
    color: {t["info"]};
    padding: 2px 8px;
    background: transparent;
}}
{label_roles_qss(t, s)}"""
