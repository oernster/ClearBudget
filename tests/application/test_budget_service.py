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


class TestBudgetServiceIncomeMonthExtras:
    """Test per-month one-off (ad-hoc) income entries."""

    def _make_service(self) -> BudgetService:
        bill_repo = FakeBillRepository()
        income_repo = FakeIncomeSourceRepository()
        payment_method_repo = FakePaymentMethodRepository()
        generator = MonthGenerator(bill_repo, income_repo)
        return BudgetService(bill_repo, income_repo, payment_method_repo, generator)

    def test_get_month_summary_includes_extra_income(self) -> None:
        """One-off income for the month is included in totals and lists."""
        service = self._make_service()
        ym = YearMonth(2026, 6)
        service.income_repo.add(
            income=IncomeSource(
                id=1,
                name="UC",
                amount=Amount(pence=200000),
                is_reliable=True,
                day_of_month=1,
            )
        )
        service.add_income_month_extra(
            income=IncomeSource(
                id=0,
                name="Tax Refund",
                amount=Amount(pence=30000),
                is_reliable=False,
                day_of_month=10,
            ),
            year_month=ym,
        )

        summary = service.get_month_summary(year_month=ym)

        assert summary.total_income.pence == 230000
        assert any(
            i.name == "Tax Refund" and i.is_month_only for i in summary.income_sources
        )
        assert any(
            i.name == "Tax Refund" and i.is_month_only
            for i in summary.all_income_sources
        )

    def test_get_month_summary_extra_only_in_its_month(self) -> None:
        """One-off income only appears in the month it was added for."""
        service = self._make_service()
        ym = YearMonth(2026, 6)
        other_ym = YearMonth(2026, 7)
        service.add_income_month_extra(
            income=IncomeSource(
                id=0,
                name="Tax Refund",
                amount=Amount(pence=30000),
                is_reliable=False,
                day_of_month=10,
            ),
            year_month=ym,
        )

        other_summary = service.get_month_summary(year_month=other_ym)

        assert not any(i.name == "Tax Refund" for i in other_summary.income_sources)

    def test_update_income_month_extra(self) -> None:
        """Updating a one-off income entry changes its values for that month."""
        service = self._make_service()
        ym = YearMonth(2026, 6)
        added = service.add_income_month_extra(
            income=IncomeSource(
                id=0,
                name="Tax Refund",
                amount=Amount(pence=30000),
                is_reliable=False,
                day_of_month=10,
            ),
            year_month=ym,
        )

        service.update_income_month_extra(
            income=IncomeSource(
                id=added.id,
                name="Tax Refund (Updated)",
                amount=Amount(pence=40000),
                is_reliable=False,
                day_of_month=12,
                is_month_only=True,
            ),
            year_month=ym,
        )

        summary = service.get_month_summary(year_month=ym)
        extra = next(i for i in summary.income_sources if i.is_month_only)
        assert extra.name == "Tax Refund (Updated)"
        assert extra.amount.pence == 40000

    def test_delete_income_month_extra(self) -> None:
        """Deleting a one-off income entry removes it from the month summary."""
        service = self._make_service()
        ym = YearMonth(2026, 6)
        added = service.add_income_month_extra(
            income=IncomeSource(
                id=0,
                name="Tax Refund",
                amount=Amount(pence=30000),
                is_reliable=False,
                day_of_month=10,
            ),
            year_month=ym,
        )

        service.delete_income_month_extra(extra_id=added.id)

        summary = service.get_month_summary(year_month=ym)
        assert not any(i.is_month_only for i in summary.income_sources)
