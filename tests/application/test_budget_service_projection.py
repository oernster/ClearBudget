"""Tests for BudgetService.get_projected_month_end_balance_pence."""

from datetime import date

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


def _make_service():
    bill_repo = FakeBillRepository()
    income_repo = FakeIncomeSourceRepository()
    pm_repo = FakePaymentMethodRepository()
    gen = MonthGenerator(bill_repo, income_repo)
    svc = BudgetService(bill_repo, income_repo, pm_repo, gen)
    return svc, bill_repo, income_repo


class TestGetProjectedMonthEndBalance:
    """Test get_projected_month_end_balance_pence — both the current-month and future-month branches."""

    def test_current_month_branch(self) -> None:
        """year_month == today_ym branch: filters income/bills with day_of_month=None (always included)."""
        svc, bill_repo, income_repo = _make_service()
        today = date.today()
        today_ym = YearMonth(today.year, today.month)

        bill_repo.add(
            bill=Bill(
                id=1,
                name="Rent",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=None,
                start_ym=YearMonth(today_ym.year, 1),
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

        summary = svc.get_month_summary(year_month=today_ym)
        # bank_balance = 0, starting = 0 (no months to project through before today)
        # day_of_month=None → always included in current-month filter
        result = svc.get_projected_month_end_balance_pence(
            year_month=today_ym, summary=summary
        )

        assert result == 100000  # 0 starting + 200k income - 100k bills

    def test_future_month_branch(self) -> None:
        """else branch fires for months beyond today_ym: uses all income/bills without day filter."""
        svc, bill_repo, income_repo = _make_service()
        today = date.today()
        today_ym = YearMonth(today.year, today.month)
        future_ym = today_ym.next_month().next_month()

        bill_repo.add(
            bill=Bill(
                id=1,
                name="Rent",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=None,
                start_ym=YearMonth(today_ym.year, 1),
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

        # _projected_starting_balance_pence accumulates: today_ym surplus + next_month surplus
        # Each month (day=None): income 200k - bills 100k = +100k
        # starting after 2 months = 200k
        summary = svc.get_month_summary(year_month=future_ym)
        result = svc.get_projected_month_end_balance_pence(
            year_month=future_ym, summary=summary
        )

        # starting=200k + else branch: income 200k - bills 100k = 300k
        assert result == 300000


class TestBalanceDayFiltering:
    """Tests for balance_day > 0 income filtering (the income-not-in-bank-yet logic)."""

    def test_solvency_balance_day_excludes_income_already_in_bank(
        self, monkeypatch
    ) -> None:
        """balance_day=5: income with day <= 5 excluded (already in bank), day > 5 included."""
        svc, bill_repo, income_repo = _make_service()
        monkeypatch.setattr(BudgetService, "_get_bank_balance_day", lambda self: 5)
        income_repo.add(
            income=IncomeSource(
                id=1,
                name="M+D",
                amount=Amount(pence=60000),
                is_reliable=True,
                day_of_month=1,
            )
        )
        income_repo.add(
            income=IncomeSource(
                id=2,
                name="UC",
                amount=Amount(pence=120000),
                is_reliable=True,
                day_of_month=21,
            )
        )
        bill_repo.add(
            bill=Bill(
                id=1,
                name="Rent",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=25,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        today = date.today()
        may = YearMonth(today.year, today.month)
        summary = svc.get_month_summary(year_month=may)
        report = svc.calculate_solvency_from_summary(
            year_month=may, month_summary=summary
        )
        # M+D day=1 <= balance_day=5 → excluded; UC day=21 > 5 → included
        # Rent day=25 >= today → included; bank_balance=0
        assert report.balance_pence == 120000 - 100000

    def test_get_projected_balance_balance_day_filters_income(
        self, monkeypatch
    ) -> None:
        """get_projected_month_end_balance_pence: balance_day > 0 filters current-month income."""
        svc, bill_repo, income_repo = _make_service()
        monkeypatch.setattr(BudgetService, "_get_bank_balance_day", lambda self: 5)
        income_repo.add(
            income=IncomeSource(
                id=1,
                name="M+D",
                amount=Amount(pence=60000),
                is_reliable=True,
                day_of_month=1,
            )
        )
        income_repo.add(
            income=IncomeSource(
                id=2,
                name="UC",
                amount=Amount(pence=120000),
                is_reliable=True,
                day_of_month=21,
            )
        )
        bill_repo.add(
            bill=Bill(
                id=1,
                name="Rent",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=25,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        today = date.today()
        today_ym = YearMonth(today.year, today.month)
        summary = svc.get_month_summary(year_month=today_ym)
        result = svc.get_projected_month_end_balance_pence(
            year_month=today_ym, summary=summary
        )
        # bank_balance=0 + UC(120000) - Rent(100000); M+D excluded (day=1 <= balance_day=5)
        assert result == 20000

    def test_projected_starting_balance_balance_day_filters_current_month_income(
        self, monkeypatch
    ) -> None:
        """_projected_starting_balance_pence: balance_day > 0 filters income for today's month."""
        svc, bill_repo, income_repo = _make_service()
        monkeypatch.setattr(BudgetService, "_get_bank_balance_day", lambda self: 5)
        income_repo.add(
            income=IncomeSource(
                id=1,
                name="M+D",
                amount=Amount(pence=60000),
                is_reliable=True,
                day_of_month=1,
            )
        )
        income_repo.add(
            income=IncomeSource(
                id=2,
                name="UC",
                amount=Amount(pence=120000),
                is_reliable=True,
                day_of_month=21,
            )
        )
        bill_repo.add(
            bill=Bill(
                id=1,
                name="Rent",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=25,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        today = date.today()
        today_ym = YearMonth(today.year, today.month)
        next_ym = today_ym.next_month()
        # Starting for next month = bank(0) + this month's remaining: UC(120k) - Rent(100k) = 20k
        # Next month solvency uses full income (180k) - bills (100k) = 80k
        report = svc.calculate_solvency(year_month=next_ym)
        assert report.balance_pence == 20000 + 180000 - 100000
