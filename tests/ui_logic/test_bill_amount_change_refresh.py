"""A saved amount change reaches the table in the same refresh as the bill.

The defect: the month view wrote the bill through the view model, which
refreshed the summary, then wrote the schedule straight to the service. A
change effective from the current month was stored and the old amount stayed
on screen until something else refreshed. Reproduced on 2026-11-04 by driving
the view model with that exact sequence: it held the old figure while the
database resolved the new one.

The view model is a QObject with signals and needs no QApplication, so these
run Qt-free like the rest of this package, over a real temp SQLite service.
"""

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.bill_amount_change import BillAmountChange
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.view_models.month_view_model import MonthViewModel

_BANK_ACCOUNT_ID = 1
_MONTH = YearMonth(2026, 11)
_ORIGINAL = Amount.from_pounds(100)
_RAISED = Amount.from_pounds(200)


def _bill() -> Bill:
    return Bill(
        id=0,
        name="Rent",
        amount=_ORIGINAL,
        payment_method_id=_BANK_ACCOUNT_ID,
        category="housing",
        bill_type="fixed",
        day_of_month=1,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
    )


def _from_this_month(amount: Amount) -> tuple[BillAmountChange, ...]:
    return (
        BillAmountChange(
            effective_year=_MONTH.year,
            effective_month=_MONTH.month,
            new_amount=amount,
        ),
    )


def _shown(view_model: MonthViewModel, bill_id: int) -> Amount:
    """The amount the table would draw: the one the view model holds."""
    return next(b for b in view_model.month_summary.all_bills if b.id == bill_id).amount


class TestEditingABillWithAChangeFromThisMonth:
    def test_the_held_summary_shows_the_new_amount(self, budget_service) -> None:
        view_model = MonthViewModel(budget_service, current_month=_MONTH)
        bill = view_model.add_bill(bill=_bill())

        view_model.update_bill(bill=bill, amount_changes=_from_this_month(_RAISED))

        assert _shown(view_model, bill.id) == _RAISED

    def test_the_schedule_is_stored(self, budget_service) -> None:
        view_model = MonthViewModel(budget_service, current_month=_MONTH)
        bill = view_model.add_bill(bill=_bill())

        view_model.update_bill(bill=bill, amount_changes=_from_this_month(_RAISED))

        assert budget_service.bill_repo.list_amount_changes(
            bill_id=bill.id
        ) == _from_this_month(_RAISED)


class TestAddingABillWithAChangeFromThisMonth:
    def test_the_held_summary_shows_the_new_amount(self, budget_service) -> None:
        view_model = MonthViewModel(budget_service, current_month=_MONTH)

        bill = view_model.add_bill(
            bill=_bill(), amount_changes=_from_this_month(_RAISED)
        )

        assert _shown(view_model, bill.id) == _RAISED


class TestAnEditThatCarriesNoSchedule:
    def test_leaves_the_stored_schedule_alone(self, budget_service) -> None:
        """An inline cell edit holds no schedule; it must not wipe one.

        None is "nothing to say about the schedule", which is different from
        an empty tuple, which is "there is no schedule".
        """
        view_model = MonthViewModel(budget_service, current_month=_MONTH)
        bill = view_model.add_bill(
            bill=_bill(), amount_changes=_from_this_month(_RAISED)
        )

        view_model.update_bill(bill=bill)

        assert _shown(view_model, bill.id) == _RAISED

    def test_an_empty_schedule_removes_the_stored_one(self, budget_service) -> None:
        """The dialog with every change removed says so with an empty tuple."""
        view_model = MonthViewModel(budget_service, current_month=_MONTH)
        bill = view_model.add_bill(
            bill=_bill(), amount_changes=_from_this_month(_RAISED)
        )

        view_model.update_bill(bill=bill, amount_changes=())

        assert _shown(view_model, bill.id) == _ORIGINAL
