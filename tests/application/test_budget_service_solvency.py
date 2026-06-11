"""Tests for BudgetService.calculate_solvency methods."""

from datetime import date

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.services._prorating import days_in_month, prorate_elapsed_pence
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from tests.application.fakes import (
    FakeBillRepository,
    FakeIncomeSourceRepository,
    FakePaymentMethodRepository,
)


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

        report = service.calculate_solvency(year_month=YearMonth.today().next_month())

        assert not report.is_solvent
        assert report.desired_acquire.pence > 100000  # At least bills + buffer

    def test_calculate_solvency_from_summary(self) -> None:
        """Test calculating solvency from provided month summary."""
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

        next_ym = YearMonth.today().next_month()
        summary = service.get_month_summary(year_month=next_ym)
        report = service.calculate_solvency_from_summary(
            year_month=next_ym,
            month_summary=summary,
        )

        today = date.today()
        elapsed = prorate_elapsed_pence(
            100000, today.day, days_in_month(today.year, today.month)
        )
        assert report.is_solvent
        # Rent (day_of_month=None) is pro-rated for the current month: the
        # elapsed portion is "freed up" compared to counting the full bill.
        assert report.balance_pence == 200000 + elapsed

    def test_calculate_solvency_from_summary_fallback(self) -> None:
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

        report = service.calculate_solvency_from_summary(
            year_month=YearMonth(2026, 6),
            month_summary=None,
        )

        assert report.is_solvent

    def test_calculate_solvency_current_month_no_balance_day(self) -> None:
        """With no bank_balance_day, income filtered by today (safe fallback)."""
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
        current = YearMonth.today()
        summary = service.get_month_summary(year_month=current)
        assert (
            service.calculate_solvency_from_summary(
                year_month=current, month_summary=summary
            ).balance_pence
            == 0
        )
        assert service.calculate_solvency(year_month=current).balance_pence == 0

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

    def test_projected_balance_two_months_ahead(self) -> None:
        """else branch in _projected_starting_balance_pence for non-current months."""
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
        two_months_ahead = YearMonth.today().next_month().next_month()
        today = date.today()
        elapsed = prorate_elapsed_pence(
            100000, today.day, days_in_month(today.year, today.month)
        )
        # Rent (day_of_month=None) is pro-rated for the current month: the
        # elapsed portion is "freed up" compared to counting the full bill.
        assert (
            service.calculate_solvency(year_month=two_months_ahead).balance_pence
            == 300000 + elapsed
        )
