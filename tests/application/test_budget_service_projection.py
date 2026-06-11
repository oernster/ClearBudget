"""Tests for BudgetService.get_projected_month_end_balance_pence."""

from datetime import date

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.services._prorating import (
    days_in_month,
    prorate_remaining_pence,
)
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
    """Test get_projected_month_end_balance_pence: both the current-month and future-month branches."""

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
        bill_repo.add(
            bill=Bill(
                id=2,
                name="Credit Card Payment",
                amount=Amount(pence=50000),
                payment_method_id=2,
                category="credit_payment",
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
        # day_of_month=None → included, pro-rated for the remainder of the month.
        # Non-bank bill (payment_method_id=2) is excluded from the bank total.
        result = svc.get_projected_month_end_balance_pence(
            year_month=today_ym, summary=summary
        )

        total_days = days_in_month(today_ym.year, today_ym.month)
        prorated_bill = prorate_remaining_pence(100000, today.day, total_days)
        assert result == 200000 - prorated_bill  # 0 starting + 200k income - bill

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
        # today_ym (current month): income 200k - prorated bill (day=None, remaining portion)
        # next_month (else branch): income 200k - bills 100k = +100k
        summary = svc.get_month_summary(year_month=future_ym)
        result = svc.get_projected_month_end_balance_pence(
            year_month=future_ym, summary=summary
        )

        total_days = days_in_month(today_ym.year, today_ym.month)
        prorated_bill = prorate_remaining_pence(100000, today.day, total_days)
        # starting = (200k - prorated_bill) + (200k - 100k)
        # else branch (future_ym): income 200k - bills 100k = 100k
        assert result == (200000 - prorated_bill) + 100000 + 100000


class TestPaidForMonthExclusion:
    """A bill marked paid_for_month is excluded from current-month bank bills."""

    def test_paid_bill_excluded_from_current_month_bank_bills(self) -> None:
        svc, bill_repo, income_repo = _make_service()
        today = date.today()
        today_ym = YearMonth(today.year, today.month)

        bill_repo.add(
            bill=Bill(
                id=1,
                name="Food",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="discretionary",
                bill_type="variable",
                day_of_month=None,
                start_ym=YearMonth(today_ym.year, 1),
                end_ym=None,
                paid_for_month=True,
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
        result = svc.get_projected_month_end_balance_pence(
            year_month=today_ym, summary=summary
        )

        # Food (no fixed day, paid) excluded entirely - no proration applied.
        assert result == 200000

    def test_paid_bill_excluded_from_current_month_solvency_filter(self) -> None:
        svc, bill_repo, income_repo = _make_service()
        today = date.today()
        today_ym = YearMonth(today.year, today.month)
        total_days = days_in_month(today_ym.year, today_ym.month)

        bill_repo.add(
            bill=Bill(
                id=1,
                name="Rent",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=total_days,
                start_ym=YearMonth(today_ym.year, 1),
                end_ym=None,
                paid_for_month=True,
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
        report = svc.calculate_solvency_from_summary(
            year_month=today_ym, month_summary=summary
        )

        # Rent (still due by date, but marked paid) excluded from solvency calc.
        assert report.balance_pence == 200000


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


class TestGetProjectedStartingBalancePence:
    """Test the public get_projected_starting_balance_pence wrapper."""

    def test_matches_private_implementation(self) -> None:
        svc, _bill_repo, _income_repo = _make_service()
        today_ym = YearMonth(date.today().year, date.today().month)

        public_result = svc.get_projected_starting_balance_pence(year_month=today_ym)
        private_result = svc._projected_starting_balance_pence(today_ym)

        assert public_result == private_result
