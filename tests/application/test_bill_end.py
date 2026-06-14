"""Tests for BudgetService.end_bill (history-safe bill end)."""

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from tests.application.fakes import (
    FakeBillRepository,
    FakeIncomeSourceRepository,
    FakePaymentMethodRepository,
)


def _service():
    bill_repo = FakeBillRepository()
    svc = BudgetService(
        bill_repo,
        FakeIncomeSourceRepository(),
        FakePaymentMethodRepository(),
        MonthGenerator(bill_repo, FakeIncomeSourceRepository()),
    )
    return svc, bill_repo


def _bill(bill_id=1):
    return Bill(
        id=bill_id,
        name="Netflix",
        amount=Amount(pence=999),
        payment_method_id=1,
        category="subscriptions",
        bill_type="fixed",
        day_of_month=1,
        start_ym=YearMonth(2000, 1),
        end_ym=None,
    )


def test_end_bill_sets_end_and_preserves_earlier_months():
    svc, bill_repo = _service()
    bill_repo.add(bill=_bill())
    # Deleted while viewing August -> ends at July (August onward dropped).
    svc.end_bill(bill_id=1, last_active_month=YearMonth(2026, 7))

    assert bill_repo.get_by_id(bill_id=1).end_ym == YearMonth(2026, 7)

    def has_bill(year, month):
        summary = svc.get_month_summary(year_month=YearMonth(year, month))
        return any(b.id == 1 for b in summary.bills)

    assert has_bill(2026, 6)  # earlier month kept
    assert has_bill(2026, 7)  # last active month kept
    assert not has_bill(2026, 8)  # dropped from here onward


def test_end_bill_missing_id_is_noop():
    svc, bill_repo = _service()
    bill_repo.add(bill=_bill())
    svc.end_bill(bill_id=999, last_active_month=YearMonth(2026, 7))
    assert bill_repo.get_by_id(bill_id=1).end_ym is None
