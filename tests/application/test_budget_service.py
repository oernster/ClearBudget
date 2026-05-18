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
