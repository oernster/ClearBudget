"""Text-entry control styling, parameterised by theme tokens.

Split from theme_qss to keep each module under the 400-LOC limit. Everything
here is a field the user types or picks a value in: line edits, the numeric and
date spin boxes and combo boxes. They share one shape (panel fill, one-pixel
border, four-by-eight padding) and one three-state border rule, so they read as
a set and belong together.

The spin BUTTONS and the calendar popup are a different concern and live in
`_theme_controls`, because they are drawn furniture rather than the field.
"""

from __future__ import annotations

# The corner radius every field is drawn with. Named because the combo's
# drop-down subcontrol has to repeat it: that subcontrol covers the right end
# of the control, so it rounds the right-hand corners or nothing does.
_FIELD_RADIUS_PX = 4


def input_qss(t: dict[str, str]) -> str:
    """Return the stylesheet for every field the user types or picks in."""
    return f"""
QLineEdit {{
    background-color: {t["panel_bg"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 4px;
    padding: 4px 8px;
}}

QLineEdit:enabled:focus {{
    border: 2px solid {t["ring"]};
}}

QLineEdit:disabled {{
    border: 2px solid {t["danger"]};
    color: {t["text_disabled"]};
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {t["panel_bg"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: 4px;
    padding: 4px 8px;
}}

QSpinBox:enabled:focus, QDoubleSpinBox:enabled:focus, QDateEdit:enabled:focus {{
    border: 2px solid {t["ring"]};
}}

QSpinBox:disabled, QDoubleSpinBox:disabled, QDateEdit:disabled {{
    border: 2px solid {t["danger"]};
    color: {t["text_disabled"]};
}}
"""


def combo_qss(t: dict[str, str]) -> str:
    """Return the combo-box stylesheet.

    Separate from `input_qss` only because the two sit either side of the
    control and widget-extra blocks in the sheet; QSS is order sensitive:
    a later rule of equal specificity wins, so the blocks keep their original
    order rather than being merged for tidiness.
    """
    return f"""
QComboBox {{
    background-color: {t["panel_bg"]};
    color: {t["text"]};
    border: 1px solid {t["border"]};
    border-radius: {_FIELD_RADIUS_PX}px;
    padding: 4px 8px;
}}

QComboBox:enabled:focus {{
    border: 2px solid {t["ring"]};
}}

QComboBox:disabled {{
    border: 2px solid {t["danger"]};
    color: {t["text_disabled"]};
}}

/* The subcontrol is made INVISIBLE here; the arrow is painted by
   ThemedComboBox instead. Qt draws this as a native button over the right
   end of the field and that button is square, so it paints across the corner
   the radius above rounds: a combo came out rounded on the left and square on
   the right, beside a line edit rounded on both. `background: transparent`
   cures that; in the same stroke it stops the platform drawing the chevron
   inside it, which is why one is painted by hand. Every other route was
   measured and rejected: `border: none` loses the arrow as well, a
   replacement built from CSS borders renders as a blank block because Qt
   paints ::down-arrow as an image; `width` (the one property that leaves the
   native arrow alone) moves it without rounding anything. */
QComboBox::drop-down {{
    background: transparent;
    border: none;
    border-top-right-radius: {_FIELD_RADIUS_PX}px;
    border-bottom-right-radius: {_FIELD_RADIUS_PX}px;
}}

"""
