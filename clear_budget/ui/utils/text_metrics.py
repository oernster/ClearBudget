"""Row heights derived from the font, rather than guessed at.

A table row was pinned to a literal 28 pixels. The application's base font is
14pt, whose line box is 26 pixels tall with a 5 pixel descent; a header
section spends padding plus a border above and below. That left 18 pixels for
26 pixels of text, so every descender was cut off at the baseline and the month
column read "Auq 2026" instead of "Aug 2026".

The number was not slightly wrong; it was unrelated to the thing it had to
contain. So it is no longer a number. `comfortable_row_height` measures the
font actually in force and adds the chrome the stylesheet actually draws, which
means the row follows the font: it stays correct when the theme changes the
family, when `ui_scale` changes the point size on a different display and when
the stylesheet's padding is edited, because both sides read the same constants.

`ensurePolished` is not optional. A stylesheet `font-size` does not reach
`QWidget.font()` until the widget is polished, so measuring an unpolished
widget silently returns the 9pt application default and reintroduces the bug.
"""

from __future__ import annotations

from PySide6.QtGui import QFontMetrics

from clear_budget.ui.theme_qss import (
    HEADER_SECTION_BORDER_PX,
    HEADER_SECTION_PADDING_PX,
    TABLE_ITEM_VPADDING_PX,
    TEXT_BREATHING_PX,
)

# A header section and a cell spend different amounts of vertical chrome; a
# row has to clear BOTH: it is one height shared by the row's cells and by its
# vertical header label. Taking the larger is what makes the row correct for
# whichever of the two is hungrier.
_ROW_CHROME_PX = 2 * max(
    HEADER_SECTION_PADDING_PX + HEADER_SECTION_BORDER_PX, TABLE_ITEM_VPADDING_PX
)


def comfortable_row_height(widget) -> int:
    """A row tall enough for `widget`'s whole line box plus the table chrome.

    Includes the descent, which is the part that was being lost, plus a
    comfort margin so the descender is not sitting exactly on the boundary.
    """
    widget.ensurePolished()
    line_box = QFontMetrics(widget.font()).height()
    return line_box + _ROW_CHROME_PX + 2 * TEXT_BREATHING_PX


def apply_comfortable_rows(table) -> None:
    """Give `table` rows that fit their text and keep them that way.

    Set on the vertical header so it governs both the cells and the row labels;
    applied at construction so no caller has to remember a magic number.
    """
    table.verticalHeader().setDefaultSectionSize(comfortable_row_height(table))
