"""Tests for BudgetService application service."""

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

class TestBudgetServiceMonthSummary:
    """Test BudgetService.get_month_summary."""

    def test_get_month_summary_surplus(self) -> None:
        """Test getting month summary with surplus."""
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        payment_method_repo = FakePaymentMethodRepository()
        generator = MonthGenerator(bill_repo, income_repo)
        service = BudgetService(bill_repo, income_repo, payment_method_repo, generator)

        # Setup bills and income
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

        summary = service.get_month_summary(year_month=YearMonth(2026, 6))

        assert summary.total_income.pence == 200000
        assert summary.total_bills.pence == 100000
        assert summary.balance.pence == 100000

    def test_get_month_summary_deficit(self) -> None:
        """Test getting month summary with deficit."""
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        payment_method_repo = FakePaymentMethodRepository()
        generator = MonthGenerator(bill_repo, income_repo)
        service = BudgetService(bill_repo, income_repo, payment_method_repo, generator)

        bill_repo.add(
            bill=Bill(
                id=1,
                name="Rent",
                amount=Amount(pence=200000),
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
                day_of_month=1,
            )
        )

        summary = service.get_month_summary(year_month=YearMonth(2026, 6))

        # Balance would be negative, but stored as 0
        assert summary.total_income.pence == 150000
        assert summary.total_bills.pence == 200000

    def test_get_month_summary_credit_card_bills_excluded_from_balance(self) -> None:
        """Test that credit card bills don't reduce bank balance."""
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        payment_method_repo = FakePaymentMethodRepository()
        generator = MonthGenerator(bill_repo, income_repo)
        service = BudgetService(bill_repo, income_repo, payment_method_repo, generator)

        # Bank bill
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
        # Credit card bill
        bill_repo.add(
            bill=Bill(
                id=2,
                name="CapitalOne Payment",
                amount=Amount(pence=50000),
                payment_method_id=2,
                category="credit_payment",
                bill_type="fixed",
                day_of_month=22,
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

        summary = service.get_month_summary(year_month=YearMonth(2026, 6))

        # Total bills includes both
        assert summary.total_bills.pence == 150000
        # Bank bills only includes the bank account bill
        assert summary.bank_bills.pence == 100000
        # Balance only deducts bank bills
        assert summary.balance.pence == 100000


class TestBudgetServiceSolvency:
    """Test BudgetService.calculate_solvency."""

    def test_calculate_solvency_solvent(self) -> None:
        """Test calculating solvency for solvent month."""
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        payment_method_repo = FakePaymentMethodRepository()
        generator = MonthGenerator(bill_repo, income_repo)
        service = BudgetService(bill_repo, income_repo, payment_method_repo, generator)

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

        report = service.calculate_solvency(year_month=YearMonth(2026, 6))

        assert report.is_solvent
        assert report.deficit.pence == 0
        assert report.desired_acquire.pence > 0  # At least buffer

    def test_calculate_solvency_projects_forward(self) -> None:
        """Test that solvency calculation considers next 2 months."""
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        payment_method_repo = FakePaymentMethodRepository()
        generator = MonthGenerator(bill_repo, income_repo)
        service = BudgetService(bill_repo, income_repo, payment_method_repo, generator)

        # Current month: surplus
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
        # Next month has extra bills
        bill_repo.add(
            bill=Bill(
                id=2,
                name="Car",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="discretionary",
                bill_type="expiring",
                day_of_month=15,
                start_ym=YearMonth(2026, 7),
                end_ym=YearMonth(2026, 7),
            )
        )
        income_repo.add(
            income=IncomeSource(
                id=1,
                name="UC",
                amount=Amount(pence=150000),
                is_reliable=True,
                day_of_month=1,
            )
        )

        report = service.calculate_solvency(year_month=YearMonth(2026, 6))

        # Should detect forward shortfall in July
        assert report.forward_shortfall.pence > 0
        assert report.desired_acquire.pence > report.buffer.pence

    def test_calculate_solvency_no_income(self) -> None:
        """Test solvency when no income sources are configured."""
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        payment_method_repo = FakePaymentMethodRepository()
        generator = MonthGenerator(bill_repo, income_repo)
        service = BudgetService(bill_repo, income_repo, payment_method_repo, generator)

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

        report = service.calculate_solvency(year_month=YearMonth(2026, 6))

        assert not report.is_solvent
        assert report.desired_acquire.pence > 100000  # At least bills + buffer

    def test_calculate_solvency_from_summary(self) -> None:
        """Test calculating solvency from provided month summary."""
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        payment_method_repo = FakePaymentMethodRepository()
        generator = MonthGenerator(bill_repo, income_repo)
        service = BudgetService(bill_repo, income_repo, payment_method_repo, generator)

        # day_of_month=25: future date (today is 19th), so not yet paid —
        # bank_balance=0 correctly represents current balance before these transactions
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
        income_repo.add(
            income=IncomeSource(
                id=1,
                name="UC",
                amount=Amount(pence=200000),
                is_reliable=True,
                day_of_month=25,
            )
        )

        summary = service.get_month_summary(year_month=YearMonth(2026, 6))
        report = service.calculate_solvency_from_summary(
            year_month=YearMonth(2026, 6),
            month_summary=summary,
        )

        assert report.is_solvent
        # bank_balance(0) + may_remaining_surplus(100000, day=25 not yet paid) + june_surplus(100000) = 200000
        assert report.balance_pence == 200000

    def test_calculate_solvency_from_summary_fallback_to_calculate_solvency(self) -> None:
        """Test that None summary falls back to calculate_solvency."""
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        payment_method_repo = FakePaymentMethodRepository()
        generator = MonthGenerator(bill_repo, income_repo)
        service = BudgetService(bill_repo, income_repo, payment_method_repo, generator)

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

        # Call with None summary
        report = service.calculate_solvency_from_summary(
            year_month=YearMonth(2026, 6),
            month_summary=None,
        )

        assert report.is_solvent

    def test_calculate_solvency_current_month_no_balance_day_uses_today_filter(self) -> None:
        """With no bank_balance_day set (FakeRepo returns 0), income filtered by today (safe fallback).
        Bills/income with day=1 (before today≈20) excluded — balance stays at bank_balance(0)."""
        bill_repo, income_repo, pm_repo = FakeBillRepository(), FakeIncomeSourceRepository(), FakePaymentMethodRepository()
        service = BudgetService(bill_repo, income_repo, pm_repo, MonthGenerator(bill_repo, income_repo))
        bill_repo.add(bill=Bill(id=1, name="Rent", amount=Amount(pence=100000), payment_method_id=1,
                                category="housing", bill_type="fixed", day_of_month=1,
                                start_ym=YearMonth(2026, 1), end_ym=None))
        income_repo.add(income=IncomeSource(id=1, name="UC", amount=Amount(pence=200000),
                                            is_reliable=True, day_of_month=1))
        may = YearMonth(2026, 5)
        summary = service.get_month_summary(year_month=may)
        assert service.calculate_solvency_from_summary(year_month=may, month_summary=summary).balance_pence == 0
        assert service.calculate_solvency(year_month=may).balance_pence == 0

    def test_projected_balance_two_months_ahead_uses_full_future_month(self) -> None:
        """else branch in _projected_starting_balance_pence fires for non-current months."""
        bill_repo, income_repo, pm_repo = FakeBillRepository(), FakeIncomeSourceRepository(), FakePaymentMethodRepository()
        service = BudgetService(bill_repo, income_repo, pm_repo, MonthGenerator(bill_repo, income_repo))
        bill_repo.add(bill=Bill(id=1, name="Rent", amount=Amount(pence=100000), payment_method_id=1,
                                category="housing", bill_type="fixed", day_of_month=25,
                                start_ym=YearMonth(2026, 1), end_ym=None))
        income_repo.add(income=IncomeSource(id=1, name="UC", amount=Amount(pence=200000),
                                            is_reliable=True, day_of_month=25))
        # May remaining(day=25>=19): +100k, June full(else): +100k, July solvency: +100k = 300k
        assert service.calculate_solvency(year_month=YearMonth(2026, 7)).balance_pence == 300000
