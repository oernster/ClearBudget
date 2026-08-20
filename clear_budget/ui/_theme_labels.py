"""Semantic label-role styling, parameterised by theme tokens.

Split from _theme_controls to keep both modules under the 400-LOC limit
(tests/structural/test_loc_limits.py). A widget carries its colour role as an
object name (see ui.label_roles) rather than an inline stylesheet, which is
what lets the whole window follow a live theme toggle: re-applying the app
stylesheet restyles every role at once, while an inline style set at build
time would keep its original colour.
"""

from __future__ import annotations

from clear_budget.ui import ui_scale
from clear_budget.ui.theme_tokens import (
    STATE_AT_RISK,
    STATE_CAUTION,
    STATE_RED,
    STATE_SAFE,
)

# The caution amber is a light fill in both themes, so its banner takes dark
# text where the other states take the usual white.
_BANNER_FG_ON_CAUTION = "#1a1a1a"
# Unscaled font sizes of the semantic label roles.
_SMALL_LABEL_FONT_PX = 12
_BODY_LABEL_FONT_PX = 16
_VALUE_LABEL_FONT_PX = 20
# Solvency tab type scale: banner, section lines, headings, breakdown detail.
# The banner size is public because the projection page paints a banner of
# its own in code (a provisional variant that carries no fill); the two must
# not drift into different sizes for the same kind of statement.
BANNER_FONT_PX = 22
_SECTION_FONT_PX = 18
_HEADING_FONT_PX = 17
_BREAKDOWN_FONT_PX = 15
# Dialog type scale: inline note, strong warning, login heading, code box.
_NOTE_FONT_PX = 11
_STRONG_WARN_FONT_PX = 14
_LOGIN_TITLE_FONT_PX = 22
_CODE_BOX_FONT_PX = 15


def label_roles_qss(t: dict[str, str], s: dict[str, str]) -> str:
    """Semantic label roles, so no view hardcodes a text colour.

    A label carries a role by object name (see ui.label_roles) rather than an
    inline stylesheet, which is what lets the whole window follow a live theme
    toggle: re-applying the stylesheet restyles every role at once, while an
    inline style set at build time would keep its original colour.
    """
    small = ui_scale.px(_SMALL_LABEL_FONT_PX)
    body = ui_scale.px(_BODY_LABEL_FONT_PX)
    value = ui_scale.px(_VALUE_LABEL_FONT_PX)
    return f"""
QLabel#LabelHint {{
    font-size: {small}px;
    font-style: italic;
    color: {t["accent"]};
    padding: 0px 5px;
}}

QLabel#LabelMuted {{
    font-size: {small}px;
    color: {t["text_muted"]};
}}

QLabel#LabelSubtle {{
    font-size: {small}px;
    color: {t["text_subtle"]};
}}

QLabel#LabelDisabled {{
    color: {t["text_disabled"]};
}}

QLabel#LabelError {{
    font-size: {small}px;
    color: {t["danger"]};
}}

QLabel#LabelTitle {{
    font-size: {value}px;
    font-weight: bold;
    color: {t["info"]};
}}

QLabel#LabelSectionTitle {{
    font-size: {body}px;
    font-weight: bold;
    color: {t["accent"]};
}}

QLabel#LabelValue {{
    font-size: {value}px;
    padding: 5px;
}}

QLabel#LabelGood {{
    font-size: {value}px;
    font-weight: bold;
    color: {t["ring"]};
    padding: 5px;
}}

QLabel#LabelWarn {{
    font-size: {value}px;
    font-weight: bold;
    color: {t["warn"]};
    padding: 5px;
}}

QLabel#LabelDanger {{
    font-size: {value}px;
    font-weight: bold;
    color: {t["danger"]};
    padding: 5px;
}}

QLabel#WarnNote, QLabel#DangerNote {{
    font-size: {small}px;
    font-weight: bold;
    padding: 0px 5px;
}}

QLabel#WarnNote {{
    color: {t["warn"]};
}}

QLabel#DangerNote {{
    color: {t["danger"]};
}}

QFrame#Separator {{
    color: {t["separator"]};
}}

/* Dialog roles: the small note under a control, the two warning weights, the
   login heading and the one-shot recovery-code box. */
QLabel#LabelNote {{
    font-size: {ui_scale.px(_NOTE_FONT_PX)}px;
    color: {t["link"]};
    padding: 2px;
}}

QLabel#LabelStrongWarn {{
    font-size: {ui_scale.px(_STRONG_WARN_FONT_PX)}px;
    font-weight: bold;
    color: {t["warn"]};
}}

QLabel#LabelChangeWarn {{
    font-size: {ui_scale.px(_SMALL_LABEL_FONT_PX)}px;
    color: {t["warn_strong"]};
}}

QLabel#LoginTitle {{
    font-size: {ui_scale.px(_LOGIN_TITLE_FONT_PX)}px;
    font-weight: bold;
    color: {t["info"]};
    margin-bottom: 4px;
}}

QTextEdit#RecoveryCodeBox {{
    font-family: monospace;
    font-size: {ui_scale.px(_CODE_BOX_FONT_PX)}px;
    background-color: {t["input_bg"]};
    color: {t["ring"]};
    border: 1px solid {t["separator"]};
    border-radius: 4px;
    padding: 6px;
}}

/* Solvency tab lines, each with its own weight in the reading order. The
   banner carries its traffic-light state as a Qt property, so the fill comes
   from the theme's state palette instead of an inline stylesheet and follows a
   live theme switch. Caution is a light fill in both themes, so it alone takes
   dark text. */
QLabel#SolvencyBanner {{
    font-size: {ui_scale.px(BANNER_FONT_PX)}px;
    font-weight: bold;
    padding: 10px;
    border-radius: 5px;
    color: {t["primary_text"]};
}}

QLabel#SolvencyBanner[state="{STATE_RED}"] {{
    background-color: {s[STATE_RED]};
}}

QLabel#SolvencyBanner[state="{STATE_AT_RISK}"] {{
    background-color: {s[STATE_AT_RISK]};
}}

QLabel#SolvencyBanner[state="{STATE_CAUTION}"] {{
    background-color: {s[STATE_CAUTION]};
    color: {_BANNER_FG_ON_CAUTION};
}}

QLabel#SolvencyBanner[state="{STATE_SAFE}"] {{
    background-color: {s[STATE_SAFE]};
}}

QLabel#SolvencyMidmonthAlert {{
    font-size: {ui_scale.px(_SECTION_FONT_PX)}px;
    font-weight: bold;
    padding: 8px;
    border-radius: 5px;
    background-color: {t["danger_strong"]};
    color: {t["primary_text"]};
}}

QLabel#SolvencySectionHeading {{
    font-size: {ui_scale.px(_HEADING_FONT_PX)}px;
    font-weight: bold;
}}

QLabel#SolvencyCommitted {{
    font-size: {ui_scale.px(_SECTION_FONT_PX)}px;
    padding: 5px;
    color: {t["text_muted"]};
}}

QLabel#SolvencyRemainingBank {{
    font-size: {ui_scale.px(_SECTION_FONT_PX)}px;
    padding: 5px;
    color: {t["warn"]};
}}

QLabel#SolvencyRemainingCard {{
    font-size: {ui_scale.px(_SECTION_FONT_PX)}px;
    padding: 5px;
    color: {t["warn_strong"]};
}}

QLabel#SolvencyBreakdown {{
    font-size: {ui_scale.px(_BREAKDOWN_FONT_PX)}px;
    padding: 5px;
    color: {t["text_muted"]};
}}

QPushButton#IconAction {{
    border: 2px solid transparent;
    background-color: transparent;
    color: {t["ring"]};
    font-size: {value}px;
    padding: 0px;
    border-radius: 4px;
}}

QPushButton#IconAction:enabled:hover, QPushButton#IconAction:enabled:focus {{
    background-color: {t["hover_fill"]};
    border: 2px solid {t["ring"]};
}}

QPushButton#IconAction:disabled {{
    border: 2px solid {t["danger"]};
}}

/* Row headers carry the pencil affordance, so they take the action colour;
   :vertical scopes it to row headers and leaves column headers muted. */
QHeaderView::section:vertical {{
    color: {t["ring"]};
}}

/* In-cell checkboxes (Active / Skip / Paid), previously styled per table. */
QTableWidget::indicator {{
    width: 15px;
    height: 15px;
    border: 2px solid {t["text_muted"]};
    border-radius: 3px;
    background: transparent;
}}

QTableWidget::indicator:checked {{
    background: {t["ring"]};
    border-color: {t["ring"]};
}}

QTableWidget::indicator:unchecked:hover {{
    border-color: {t["checkbox_hover"]};
}}
"""
