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
from clear_budget.ui._theme_labels_solvency import solvency_label_roles_qss
from clear_budget.ui.theme_tokens import STATE_SAFE

# Unscaled font sizes of the semantic label roles.
_SMALL_LABEL_FONT_PX = 12
_BODY_LABEL_FONT_PX = 16
_VALUE_LABEL_FONT_PX = 20
# Solvency view type scale: banner, section lines, headings, breakdown detail.
_SECTION_FONT_PX = 18
_HEADING_FONT_PX = 17
_BREAKDOWN_FONT_PX = 15
# Page-body label padding. Public because the Recommendations rows align a
# checkbox to their label's first text line and must know where it starts.
BODY_PADDING_PX = 5
# Dialog type scale: inline note, strong warning, login heading, code box.
_NOTE_FONT_PX = 11
_STRONG_WARN_FONT_PX = 14
_LOGIN_TITLE_FONT_PX = 22
# The signed-in account, shown at the left of the month tray. Sized with
# the month beside it: it names WHOSE budget is on screen, which is worth
# as much as which month it is.
_NAV_USER_FONT_PX = 20
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
    solvency = solvency_label_roles_qss(
        t,
        s,
        section_px=ui_scale.px(_SECTION_FONT_PX),
        breakdown_px=ui_scale.px(_BREAKDOWN_FONT_PX),
        heading_px=ui_scale.px(_HEADING_FONT_PX),
    )
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

/* Page body text, sized on the Solvency scale so every reading page shares
   one type ramp: paragraphs at the section size, captions at the breakdown
   size. Rich text inside a body label gets its h3 weight from Qt, landing
   beside the Solvency banner. */
QLabel#LabelBody {{
    font-size: {ui_scale.px(_SECTION_FONT_PX)}px;
    padding: {ui_scale.px(BODY_PADDING_PX)}px;
}}

QLabel#LabelBodyDetail {{
    font-size: {ui_scale.px(_BREAKDOWN_FONT_PX)}px;
    padding: {ui_scale.px(BODY_PADDING_PX)}px;
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
    color: {s[STATE_SAFE]};
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

QLabel#NavUserLabel {{
    font-size: {ui_scale.px(_NAV_USER_FONT_PX)}px;
    font-weight: bold;
    color: {t["text"]};
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

{solvency}
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
    background: {t["checked_fill"]};
    border-color: {t["checked_fill"]};
}}

QTableWidget::indicator:unchecked:hover {{
    border-color: {t["checkbox_hover"]};
}}
"""
