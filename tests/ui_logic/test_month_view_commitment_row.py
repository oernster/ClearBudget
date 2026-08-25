"""Qt-free guard: a commitment reminder is never mistaken for a bill.

The Monthly Budget's bills table carries a reminder row for each commitment
due that month, so the same obligation is not entered twice. That row sits in
the same table as the real bills and every edit and delete path in the view
starts at `_get_bill_from_row`.

The danger is specific and quiet. A reminder row carries no bill id, so an
unguarded lookup would answer with whatever bill happened to match; the
user would then edit or delete something they never selected. This test pins the
refusal at the one place that can make it.
"""

from types import SimpleNamespace

from clear_budget.ui.views._month_view_table_mixin import COMMITMENT_ROLE
from clear_budget.ui.views.month_view import MonthView

_BILL_ID = 7


class _Item:
    """A table cell, in place of a QTableWidgetItem."""

    def __init__(self, data: dict) -> None:
        self._data = data

    def data(self, role):
        return self._data.get(role)


class _Table:
    def __init__(self, rows: dict) -> None:
        self._rows = rows

    def item(self, row, _column):
        return self._rows.get(row)


class _View(MonthView):
    """MonthView's row lookup alone, with no Qt underneath it."""

    def __init__(self, rows, bills) -> None:
        self.bills_table = _Table(rows)
        self.view_model = SimpleNamespace(
            month_summary=SimpleNamespace(all_bills=bills)
        )


def _bill(bill_id=_BILL_ID):
    return SimpleNamespace(id=bill_id, name="Rent")


def _view(rows, bills=None):
    return _View(rows, [_bill()] if bills is None else bills)


class TestARealBillStillResolves:
    def test_a_bill_row_answers_with_its_bill(self):
        from PySide6.QtCore import Qt

        rows = {0: _Item({Qt.ItemDataRole.UserRole: _BILL_ID})}
        assert _view(rows)._get_bill_from_row(0).id == _BILL_ID


class TestAReminderIsRefused:
    def test_a_commitment_row_answers_with_nothing(self):
        rows = {0: _Item({COMMITMENT_ROLE: True})}
        assert _view(rows)._get_bill_from_row(0) is None

    def test_it_is_refused_even_when_it_carries_a_matching_id(self):
        """The failure this exists to prevent: editing a bill nobody selected."""
        from PySide6.QtCore import Qt

        rows = {0: _Item({Qt.ItemDataRole.UserRole: _BILL_ID, COMMITMENT_ROLE: True})}
        assert _view(rows)._get_bill_from_row(0) is None


class TestTheOtherRefusals:
    """Kept beside the new one, because they share the single exit."""

    def test_a_negative_row_answers_with_nothing(self):
        assert _view({})._get_bill_from_row(-1) is None

    def test_an_empty_cell_answers_with_nothing(self):
        assert _view({})._get_bill_from_row(0) is None

    def test_an_unknown_id_answers_with_nothing(self):
        from PySide6.QtCore import Qt

        rows = {0: _Item({Qt.ItemDataRole.UserRole: 999})}
        assert _view(rows)._get_bill_from_row(0) is None
