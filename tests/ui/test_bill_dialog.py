"""Headless smoke tests for the bill dialog's optional end-month field."""

from PySide6.QtCore import QDate

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.widgets.bill_dialog import BillDialog


def _bill(end_ym=None):
    return Bill(
        id=5,
        name="Spotify",
        amount=Amount(pence=1199),
        payment_method_id=1,
        category="subscriptions",
        bill_type="fixed",
        day_of_month=3,
        start_ym=YearMonth(2000, 1),
        end_ym=end_ym,
    )


def test_new_bill_has_no_end_by_default(qapplication) -> None:
    dialog = BillDialog(None, None, current_month=YearMonth(2026, 8))
    dialog.name_edit.setText("Gym")
    dialog.amount_edit.setText("20.00")
    assert dialog.get_bill().end_ym is None


def test_setting_end_month_round_trips(qapplication) -> None:
    dialog = BillDialog(None, None, current_month=YearMonth(2026, 8))
    dialog.name_edit.setText("Gym")
    dialog.amount_edit.setText("20.00")
    dialog.ends_check.setChecked(True)
    dialog.end_date_edit.setDate(QDate(2027, 3, 1))
    assert dialog.get_bill().end_ym == YearMonth(2027, 3)


def test_existing_end_month_loads_checked(qapplication) -> None:
    dialog = BillDialog(
        None, _bill(end_ym=YearMonth(2026, 10)), current_month=YearMonth(2026, 8)
    )
    assert dialog.ends_check.isChecked()
    assert dialog.get_bill().end_ym == YearMonth(2026, 10)
