"""The ring reaches a table from the keyboard and from nowhere else.

A table's default focus policy is `StrongFocus`, which grants CLICK focus as
well. So clicking anywhere in a table put the green ring around the whole pane:
clicking a row did it; so did clicking the empty space below the last row,
where a click selects nothing and does nothing. A pane outlined for no reason
reads as a control the user has activated; the next Tab then carried on
from a place they had not chosen.

`TabFocus` says the same thing the page body already says
(`ScrollableTab._scroll`): focus arrives here from the ring, never from the
pointer. What a click does is unchanged, which is the point. Selection is not
focus: clicking a row still selects it and still arms Delete (measured on both
policies, with the row selected either way); once the ring does arrive the
table keeps Up and Down for its rows.

The same rule for buttons lives in `KeyboardNavigator._focus_arriving`, which
refuses mouse-reason focus outright. A table cannot be handled there because a
click on one is meaningful; it is the RING that must not follow.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView


def keyboard_only_focus(table: QAbstractItemView) -> None:
    """Let `table` take focus from the ring, never from a click."""
    table.setFocusPolicy(Qt.FocusPolicy.TabFocus)
