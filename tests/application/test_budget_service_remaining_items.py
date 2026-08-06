"""Tests for BudgetService.get_remaining_month_items.

Split out of test_budget_service_solvency.py, which was at 387 lines and so one
edit away from failing the size cap.
"""

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from tests.application.fakes import (
    FakeBillRepository,
    FakeIncomeSourceRepository,
    FakePaymentMethodRepository,
)


class TestBudgetServiceRemainingMonthItems:
    """Test BudgetService.get_remaining_month_items."""

    def test_get_remaining_month_items_current_month(self) -> None:
        """Current month: items already due before today are excluded."""
        bill_repo, income_repo, pm_repo = (
            FakeBillRepository(),
            FakeIncomeSourceRepository(),
            FakePaymentMethodRepository(),
        )
        service = BudgetService(
            bill_repo, income_repo, pm_repo, MonthGenerator(bill_repo, income_repo)
        )
        bill_repo.add(
            bill=Bill(
                id=1,
                name="Food",
                amount=Amount(pence=20000),
                payment_method_id=1,
                category="groceries",
                bill_type="variable",
                day_of_month=None,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        income_repo.add(
            income=IncomeSource(
                id=1,
                name="UC",
                amount=Amount(pence=200000),
                is_reliable=True,
                day_of_month=None,
            )
        )
        current = YearMonth.today()
        summary = service.get_month_summary(year_month=current)
        bills, income = service.get_remaining_month_items(
            year_month=current, summary=summary
        )
        assert [b.name for b in bills] == ["Food"]
        assert [i.name for i in income] == ["UC"]

    def test_get_remaining_month_items_other_month_unchanged(self) -> None:
        """Non-current month: all bills/income returned, no day-based filtering."""
        bill_repo, income_repo, pm_repo = (
            FakeBillRepository(),
            FakeIncomeSourceRepository(),
            FakePaymentMethodRepository(),
        )
        service = BudgetService(
            bill_repo, income_repo, pm_repo, MonthGenerator(bill_repo, income_repo)
        )
        bill_repo.add(
            bill=Bill(
                id=1,
                name="Rent",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        income_repo.add(
            income=IncomeSource(
                id=1,
                name="UC",
                amount=Amount(pence=200000),
                is_reliable=True,
                day_of_month=1,
            )
        )
        next_ym = YearMonth.today().next_month()
        summary = service.get_month_summary(year_month=next_ym)
        bills, income = service.get_remaining_month_items(
            year_month=next_ym, summary=summary
        )
        assert [b.name for b in bills] == ["Rent"]
        assert [i.name for i in income] == ["UC"]
