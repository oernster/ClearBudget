"""Wrapping a filesystem path for display in a message box.

Qt wraps a long path wherever it finds a break opportunity, which for
`C:\\Users\\Oliver\\AppData\\Local\\ClearBudget\\clearbudget_backup.db` means
a first line holding `C:` alone and a remainder that runs off the side of the
dialog. Qt is not wrong; it simply has no idea the string is a path.

So the wrapping is done here instead, before the text reaches the label: the
break falls after a separator, the separator stays at the end of the line it
belongs to and the drive or UNC prefix is carried with the first segment so it
is never stranded on a line of its own. Every line is measured with the
label's own font, so the result is right at any UI scale.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QFontMetrics

from clear_budget.ui import ui_scale

# The width a path label is wrapped and sized to, at scale factor 1. Wide
# enough for a typical AppData path on two lines, narrow enough that the
# dialog stays a dialog.
PATH_LABEL_WIDTH = 460

_SEPARATORS = "\\/"


def _tokens(text: str) -> list[str]:
    """`text` split after every separator, the separator kept on its piece."""
    tokens: list[str] = []
    piece = ""
    for char in text:
        piece += char
        if char in _SEPARATORS:
            tokens.append(piece)
            piece = ""
    if piece:
        tokens.append(piece)
    return tokens


def _merge_prefix(tokens: list[str]) -> list[str]:
    """Fold a leading `C:\\` or UNC `\\\\` into the segment that follows it.

    A prefix carries no name of its own, so a line holding only one says
    nothing; folding it forward is what stops `C:` sitting alone.
    """
    merged = list(tokens)
    while len(merged) > 1:
        body = merged[0].rstrip(_SEPARATORS)
        if body and not body.endswith(":"):
            break
        merged[1] = merged[0] + merged[1]
        del merged[0]
    return merged


def wrap_path(text: str, max_width: int, width_of: Callable[[str], int]) -> str:
    """`text` broken at separators into lines no wider than `max_width`.

    `width_of` measures a candidate line in the same units as `max_width`. A
    single segment wider than the whole line is left whole, because breaking
    mid-name would read as two different names.
    """
    lines: list[str] = []
    current = ""
    for token in _merge_prefix(_tokens(text)):
        if current and width_of(current + token) > max_width:
            lines.append(current)
            current = token
        else:
            current += token
    if current:
        lines.append(current)
    return "\n".join(lines)


def wrap_for(widget, text: str) -> str:
    """`text` wrapped to the path label width in `widget`'s own font."""
    advance = QFontMetrics(widget.font()).horizontalAdvance
    return wrap_path(text, ui_scale.px(PATH_LABEL_WIDTH), advance)
