"""Tests for month archiving with real database."""

import pytest

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)


class TestArchiveMonth:
    """Test archiving months to database."""

    def test_archive_month_records_month(self, db) -> None:
        """Archiving a month records it so the Archive tab can list it."""
        bill_repo = SQLiteBillRepository(db.conn)
        income_repo = SQLiteIncomeSourceRepository(db.conn)
        payment_method_repo = SQLitePaymentMethodRepository(db.conn)
        generator = MonthGenerator(bill_repo, income_repo)
        service = BudgetService(bill_repo, income_repo, payment_method_repo, generator)

        # Setup bills and income
        bill_repo.add(
            bill=Bill(
                id=0,
                name="Rent",
                amount=Amount(pence=135000),
                payment_method_id=1,
                category="housing",
                bill_type="fixed",
                day_of_month=19,
                start_ym=YearMonth(2026, 1),
                end_ym=None,
            )
        )
        income_repo.add(
            income=IncomeSource(
                id=0,
                name="UC",
                amount=Amount(pence=120000),
                is_reliable=True,
                day_of_month=21,
            )
        )

        # Archive May 2026
        service.archive_month(year_month=YearMonth(2026, 5))

        # Verify recorded months includes May
        recorded = service.get_recorded_months()
        assert YearMonth(2026, 5) in recorded

    def test_archive_month_is_idempotent(self, db) -> None:
        """Test that archiving same month twice is safe."""
        bill_repo = SQLiteBillRepository(db.conn)
        income_repo = SQLiteIncomeSourceRepository(db.conn)
        payment_method_repo = SQLitePaymentMethodRepository(db.conn)
        generator = MonthGenerator(bill_repo, income_repo)
        service = BudgetService(bill_repo, income_repo, payment_method_repo, generator)

        bill_repo.add(
            bill=Bill(
                id=0,
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

        # Archive twice
        service.archive_month(year_month=YearMonth(2026, 5))
        service.archive_month(year_month=YearMonth(2026, 5))

        # Should still have exactly one May
        recorded = service.get_recorded_months()
        may_count = sum(1 for m in recorded if m == YearMonth(2026, 5))
        assert may_count == 1

    def test_archive_multiple_months(self, db) -> None:
        """Test archiving multiple different months."""
        bill_repo = SQLiteBillRepository(db.conn)
        income_repo = SQLiteIncomeSourceRepository(db.conn)
        payment_method_repo = SQLitePaymentMethodRepository(db.conn)
        generator = MonthGenerator(bill_repo, income_repo)
        service = BudgetService(bill_repo, income_repo, payment_method_repo, generator)

        bill_repo.add(
            bill=Bill(
                id=0,
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

        # Archive multiple months
        service.archive_month(year_month=YearMonth(2026, 3))
        service.archive_month(year_month=YearMonth(2026, 5))
        service.archive_month(year_month=YearMonth(2026, 6))

        recorded = service.get_recorded_months()
        assert YearMonth(2026, 3) in recorded
        assert YearMonth(2026, 5) in recorded
        assert YearMonth(2026, 6) in recorded

    def _service_with_rent(self, db) -> BudgetService:
        bill_repo = SQLiteBillRepository(db.conn)
        income_repo = SQLiteIncomeSourceRepository(db.conn)
        payment_method_repo = SQLitePaymentMethodRepository(db.conn)
        generator = MonthGenerator(bill_repo, income_repo)
        service = BudgetService(bill_repo, income_repo, payment_method_repo, generator)
        bill_repo.add(
            bill=Bill(
                id=0,
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
        return service

    def test_auto_archive_seeds_previous_month_when_nothing_recorded(self, db) -> None:
        """With no history yet, the month that just ended is archived, and no
        earlier month is fabricated."""
        service = self._service_with_rent(db)
        current = YearMonth(2026, 7)

        service.auto_archive_elapsed_months(current_month=current)

        recorded = service.get_recorded_months()
        assert YearMonth(2026, 6) in recorded  # the month that just ended
        assert YearMonth(2026, 5) not in recorded  # no history fabricated further back
        assert current not in recorded  # the live month is never archived

    def test_auto_archive_fills_the_gap_from_earliest_record(self, db) -> None:
        """The reported bug: May was recorded but June was lost. Catch-up
        archives every elapsed month from the earliest record up to the live
        month, recovering June (and any other gap)."""
        service = self._service_with_rent(db)
        service.archive_month(year_month=YearMonth(2026, 5))

        service.auto_archive_elapsed_months(current_month=YearMonth(2026, 8))

        recorded = service.get_recorded_months()
        assert YearMonth(2026, 5) in recorded
        assert YearMonth(2026, 6) in recorded  # was lost, now recovered
        assert YearMonth(2026, 7) in recorded
        assert YearMonth(2026, 8) not in recorded  # the live month stays open

    def test_auto_archive_is_idempotent_across_relaunches(self, db) -> None:
        """Running it again on the same month adds nothing (safe every launch)."""
        service = self._service_with_rent(db)
        current = YearMonth(2026, 7)

        service.auto_archive_elapsed_months(current_month=current)
        first = service.get_recorded_months()
        service.auto_archive_elapsed_months(current_month=current)
        second = service.get_recorded_months()

        assert sorted(first) == sorted(second)
