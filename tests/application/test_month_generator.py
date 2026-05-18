"""Tests for MonthGenerator service."""

from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from tests.application.fakes import FakeBillRepository, FakeIncomeSourceRepository


class TestMonthGeneratorBills:
    """Test MonthGenerator bill generation."""

    def test_generate_month_bills_from_templates(self) -> None:
        """Test generating MonthBill instances from templates."""
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        generator = MonthGenerator(bill_repo, income_repo)

        # Add template bills
        bill_repo.add(
            bill=Bill(
                id=1,
                name="Rent",
                amount=Amount(pence=135000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        bill_repo.add(
            bill=Bill(
                id=2,
                name="Utilities",
                amount=Amount(pence=5000),
                payment_method_id=1,
                category="utilities",
                bill_type="fixed",
                day_of_month=15,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )

        # Generate month bills
        month_bills = generator.generate_month_bills(
            year_month=YearMonth(2026, 6),
            month_id=1,
        )

        assert len(month_bills) == 2
        assert month_bills[0].name == "Rent"
        assert month_bills[1].name == "Utilities"

    def test_generate_bills_respects_date_range(self) -> None:
        """Test that only bills active in the month are generated."""
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        generator = MonthGenerator(bill_repo, income_repo)

        # Add bills with different date ranges
        bill_repo.add(
            bill=Bill(
                id=1,
                name="Always",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=1,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        bill_repo.add(
            bill=Bill(
                id=2,
                name="Only June",
                amount=Amount(pence=5000),
                payment_method_id=1,
                category="utilities",
                bill_type="expiring",
                day_of_month=15,
                start_ym=YearMonth(2026, 6),
                end_ym=YearMonth(2026, 6),
            )
        )

        # June should have both
        june_bills = generator.generate_month_bills(
            year_month=YearMonth(2026, 6),
            month_id=1,
        )
        assert len(june_bills) == 2

        # July should have only the first
        july_bills = generator.generate_month_bills(
            year_month=YearMonth(2026, 7),
            month_id=2,
        )
        assert len(july_bills) == 1
        assert july_bills[0].name == "Always"


class TestMonthGeneratorIncome:
    """Test MonthGenerator income generation."""

    def test_generate_month_income_from_sources(self) -> None:
        """Test generating MonthIncome from sources."""
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        generator = MonthGenerator(bill_repo, income_repo)

        # Add income sources
        income_repo.add(
            income=IncomeSource(
                id=1,
                name="UC",
                amount=Amount(pence=120000),
                is_reliable=True,
                day_of_month=1,
            )
        )
        income_repo.add(
            income=IncomeSource(
                id=2,
                name="Freelance",
                amount=Amount(pence=50000),
                is_reliable=False,
                day_of_month=None,
            )
        )

        month_income = generator.generate_month_income(
            year_month=YearMonth(2026, 6),
            month_id=1,
        )

        assert len(month_income) == 2
        assert month_income[0].name == "UC"
        assert month_income[1].name == "Freelance"

    def test_generate_income_skips_inactive(self) -> None:
        """Test that only active income sources are included."""
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        generator = MonthGenerator(bill_repo, income_repo)

        income_repo.add(
            income=IncomeSource(
                id=1,
                name="Active",
                amount=Amount(pence=100000),
                is_reliable=True,
                day_of_month=1,
            )
        )
        income_repo.add(
            income=IncomeSource(
                id=2,
                name="Inactive",
                amount=Amount.zero(),
                is_reliable=False,
                day_of_month=None,
                active=False,
            )
        )

        month_income = generator.generate_month_income(
            year_month=YearMonth(2026, 6),
            month_id=1,
        )

        assert len(month_income) == 1
        assert month_income[0].name == "Active"
