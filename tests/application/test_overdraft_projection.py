"""Tests for BudgetService.first_overdrawn_month and the projection helper."""

from clear_budget.application.services._overdraft_projection import (
    first_overdrawn_month,
)
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


def _service(*, income_pence: int, bank_bill_pence: int) -> BudgetService:
    """Service whose every month nets income_pence minus bank_bill_pence."""
    bill_repo = FakeBillRepository()
    income_repo = FakeIncomeSourceRepository()
    bill_repo.add(
        bill=Bill(
            id=1,
            name="Rent",
            amount=Amount(pence=bank_bill_pence),
            payment_method_id=1,
            category="housing",
            bill_type="fixed",
            day_of_month=None,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
    )
    income_repo.add(
        income=IncomeSource(
            id=1,
            name="UC",
            amount=Amount(pence=income_pence),
            is_reliable=True,
            day_of_month=None,
        )
    )
    return BudgetService(
        bill_repo,
        income_repo,
        FakePaymentMethodRepository(),
        MonthGenerator(bill_repo, income_repo),
    )


def test_deficit_returns_first_negative_month() -> None:
    # Net -500/month; from 900 at end of July: Aug 400, Sep -100.
    svc = _service(income_pence=100000, bank_bill_pence=150000)
    result = svc.first_overdrawn_month(
        from_year_month=YearMonth(2026, 7), from_balance_pence=90000
    )
    assert result == YearMonth(2026, 9)


def test_surplus_returns_none() -> None:
    # Net +500/month: the balance only grows, never overdrawn within the horizon.
    svc = _service(income_pence=150000, bank_bill_pence=100000)
    result = svc.first_overdrawn_month(
        from_year_month=YearMonth(2026, 7), from_balance_pence=0
    )
    assert result is None


def test_overdraft_beyond_horizon_returns_none() -> None:
    # Net -500/month from 600: Aug +100, Sep -400. A horizon of 1 stops at Aug.
    svc = _service(income_pence=100000, bank_bill_pence=150000)
    result = first_overdrawn_month(
        get_month_summary=svc.get_month_summary,
        from_year_month=YearMonth(2026, 7),
        from_balance_pence=60000,
        horizon_months=1,
    )
    assert result is None


def test_overdraft_within_horizon_returns_month() -> None:
    # Same slide, but a horizon of 2 reaches September.
    svc = _service(income_pence=100000, bank_bill_pence=150000)
    result = first_overdrawn_month(
        get_month_summary=svc.get_month_summary,
        from_year_month=YearMonth(2026, 7),
        from_balance_pence=60000,
        horizon_months=2,
    )
    assert result == YearMonth(2026, 9)


def test_midmonth_dip_with_positive_close_is_flagged() -> None:
    # A big early bill then late income: the month dips below zero on day 1, then
    # a day-20 payment lifts it to a positive close. A month-end-only check would
    # wrongly skip it; the day-by-day projection must flag it.
    bill_repo = FakeBillRepository()
    income_repo = FakeIncomeSourceRepository()
    bill_repo.add(
        bill=Bill(
            id=1,
            name="Rent",
            amount=Amount(pence=120000),
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
            amount=Amount(pence=150000),
            is_reliable=True,
            day_of_month=20,
        )
    )
    svc = BudgetService(
        bill_repo,
        income_repo,
        FakePaymentMethodRepository(),
        MonthGenerator(bill_repo, income_repo),
    )
    # August opens at 500: day 1 -1200 -> -700 (overdrawn), day 20 +1500 -> +800 close.
    result = svc.first_overdrawn_month(
        from_year_month=YearMonth(2026, 7), from_balance_pence=50000
    )
    assert result == YearMonth(2026, 8)
