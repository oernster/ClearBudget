"""The click-a-heading ordering shared by the tables that carry it.

The pages themselves need a QApplication and are out of this suite's reach
(see tests/conftest.py), so what is pinned here is the part that decides the
answer: which column a click moves to, which way it points afterwards and the
order the rows come back in. The three views differ only in the keys they
hand it.
"""

from __future__ import annotations

from clear_budget.ui.utils.table_sort import (
    NO_COLUMN,
    UNSORTED,
    SortState,
    sorted_rows,
)

_KEYS = {0: lambda row: row["name"], 1: lambda row: row["amount"]}
_ROWS = (
    {"name": "Zebra", "amount": 300},
    {"name": "Apple", "amount": 900},
    {"name": "Mango", "amount": 100},
)


def _names(rows) -> list[str]:
    return [row["name"] for row in rows]


def test_a_first_click_moves_to_the_column_and_starts_ascending() -> None:
    assert UNSORTED.toggled(2) == SortState(column=2, ascending=True)


def test_a_second_click_on_the_same_column_reverses_it() -> None:
    once = UNSORTED.toggled(2)
    assert once.toggled(2) == SortState(column=2, ascending=False)


def test_a_click_on_another_column_starts_ascending_again() -> None:
    """A first look at a column asks for it ascending, whatever came before."""
    descending = SortState(column=2, ascending=False)
    assert descending.toggled(3) == SortState(column=3, ascending=True)


def test_the_rows_come_back_in_the_order_the_column_asks_for() -> None:
    ascending = sorted_rows(_ROWS, SortState(column=1), _KEYS)
    assert _names(ascending) == ["Mango", "Zebra", "Apple"]
    descending = sorted_rows(_ROWS, SortState(column=1, ascending=False), _KEYS)
    assert _names(descending) == ["Apple", "Zebra", "Mango"]


def test_a_column_with_no_ordering_leaves_the_rows_alone() -> None:
    """Answering a click by sorting on some OTHER column is a wrong table."""
    assert _names(sorted_rows(_ROWS, SortState(column=9), _KEYS)) == _names(_ROWS)


def test_a_table_nobody_has_sorted_is_left_in_the_order_it_arrived() -> None:
    assert UNSORTED.column == NO_COLUMN
    assert _names(sorted_rows(_ROWS, UNSORTED, _KEYS)) == _names(_ROWS)


def test_the_returned_rows_are_a_new_list_either_way() -> None:
    """A view assigns the result back over its own rows, so it must be one."""
    rows = list(_ROWS)
    assert sorted_rows(rows, UNSORTED, _KEYS) is not rows
    assert sorted_rows(rows, SortState(column=0), _KEYS) is not rows
