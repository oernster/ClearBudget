"""Click a column heading to order a table by it.

Monthly Budget already ordered its two tables this way; nothing on screen
said so. A heading that reorders the page on a click and gives no sign of it
reads as a page that moved on its own, so the arrow is part of the mechanism
rather than a decoration on top of it: the sorted column shows which way it
is pointing; every table that sorts shows it the same way.

The state is a value, so a view holds one per table rather than a pair of
loose attributes; the pure half (which column, which way, what order that
puts the rows in) carries no Qt at all, so it can be reasoned about and
tested without a widget.

The ordering is applied to the rows BEFORE they are written into the table,
never by Qt's own sorting: a view that maps a row index back to the record it
came from would be reading the wrong record the moment Qt reordered the cells
underneath it.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt

# A table that has not been sorted by hand yet, still in the order its data
# arrived in. Clicking a heading leaves this state and never returns to it.
NO_COLUMN = -1


@dataclass(frozen=True, slots=True)
class SortState:
    """Which column a table is ordered by; which way it runs."""

    column: int
    ascending: bool = True

    def toggled(self, column: int) -> SortState:
        """The state after a click on `column`.

        Clicking the column already sorted reverses it; clicking any other
        column moves to it and starts ascending, which is what a first look
        at a column asks for.
        """
        if column == self.column:
            return SortState(column, not self.ascending)
        return SortState(column, True)

    @property
    def order(self) -> Qt.SortOrder:
        """The direction, as the header's own indicator states it."""
        if self.ascending:
            return Qt.SortOrder.AscendingOrder
        return Qt.SortOrder.DescendingOrder


UNSORTED = SortState(column=NO_COLUMN)


def sorted_rows(rows, state: SortState, keys: dict) -> list:
    """`rows` in the order `state` asks for, read through `keys`.

    A column with no key in `keys` carries no ordering of its own, so the
    rows are handed back untouched rather than quietly falling back to some
    other column, which would answer a click with the wrong table.
    """
    key = keys.get(state.column)
    if key is None:
        return list(rows)
    return sorted(rows, key=key, reverse=not state.ascending)


def show_sort_indicator(header, state: SortState) -> None:
    """Point the header's arrow at the column the rows are ordered by.

    The header is a `SortHeaderView`, which draws that arrow itself beside the
    heading text; the platform's own indicator is a few pixels at the top edge
    of the section and was read as no answer at all. A table still in the
    order its data arrived in shows no arrow, since an arrow on a column
    nobody chose would claim an ordering the table has not been given.
    """
    header.show_sort(state)
