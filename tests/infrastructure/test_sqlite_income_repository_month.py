"""Tests for SQLiteIncomeSourceRepository month extras and list_active_for_month."""

from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)


class TestSQLiteIncomeSourceMonthExtras:
    """Test per-month one-off (ad-hoc) income entries."""

    def test_add_month_extra(self, db) -> None:
        """Test adding a one-off income entry for a month."""
        repo = SQLiteIncomeSourceRepository(db.conn)
        ym = YearMonth(2026, 6)

        added = repo.add_month_extra(
            year_month=ym,
            income=IncomeSource(
                id=0,
                name="Tax Refund",
                amount=Amount(pence=30000),
                is_reliable=False,
                day_of_month=10,
            ),
        )

        assert added.id > 0
        assert added.name == "Tax Refund"
        assert added.is_month_only is True

    def test_list_extras_for_month(self, db) -> None:
        """Test listing one-off income entries for a specific month."""
        repo = SQLiteIncomeSourceRepository(db.conn)
        ym = YearMonth(2026, 6)
        other_ym = YearMonth(2026, 7)

        repo.add_month_extra(
            year_month=ym,
            income=IncomeSource(
                id=0,
                name="Tax Refund",
                amount=Amount(pence=30000),
                is_reliable=False,
                day_of_month=10,
            ),
        )
        repo.add_month_extra(
            year_month=other_ym,
            income=IncomeSource(
                id=0,
                name="Bonus",
                amount=Amount(pence=50000),
                is_reliable=False,
                day_of_month=None,
            ),
        )

        extras = repo.list_extras_for_month(year_month=ym)

        assert len(extras) == 1
        assert extras[0].name == "Tax Refund"
        assert extras[0].is_month_only is True
        assert extras[0].active is True

    def test_list_extras_for_month_empty(self, db) -> None:
        """Test listing extras for a month with none returns empty list."""
        repo = SQLiteIncomeSourceRepository(db.conn)
        extras = repo.list_extras_for_month(year_month=YearMonth(2026, 6))
        assert extras == []

    def test_update_month_extra(self, db) -> None:
        """Test updating a one-off income entry."""
        repo = SQLiteIncomeSourceRepository(db.conn)
        ym = YearMonth(2026, 6)

        added = repo.add_month_extra(
            year_month=ym,
            income=IncomeSource(
                id=0,
                name="Tax Refund",
                amount=Amount(pence=30000),
                is_reliable=False,
                day_of_month=10,
            ),
        )

        updated = IncomeSource(
            id=added.id,
            name="Tax Refund (Updated)",
            amount=Amount(pence=35000),
            is_reliable=True,
            day_of_month=15,
            is_month_only=True,
        )
        repo.update_month_extra(year_month=ym, income=updated)

        extras = repo.list_extras_for_month(year_month=ym)
        assert len(extras) == 1
        assert extras[0].name == "Tax Refund (Updated)"
        assert extras[0].amount.pence == 35000
        assert extras[0].is_reliable is True
        assert extras[0].day_of_month == 15

    def test_delete_month_extra(self, db) -> None:
        """Test deleting a one-off income entry."""
        repo = SQLiteIncomeSourceRepository(db.conn)
        ym = YearMonth(2026, 6)

        added = repo.add_month_extra(
            year_month=ym,
            income=IncomeSource(
                id=0,
                name="Tax Refund",
                amount=Amount(pence=30000),
                is_reliable=False,
                day_of_month=10,
            ),
        )

        repo.delete_month_extra(extra_id=added.id)

        extras = repo.list_extras_for_month(year_month=ym)
        assert extras == []

    def test_mark_and_unmark_extra_received(self, db) -> None:
        """Test marking and unmarking a one-off income entry as received."""
        repo = SQLiteIncomeSourceRepository(db.conn)
        ym = YearMonth(2026, 6)

        added = repo.add_month_extra(
            year_month=ym,
            income=IncomeSource(
                id=0,
                name="Tax Refund",
                amount=Amount(pence=30000),
                is_reliable=False,
                day_of_month=10,
            ),
        )

        repo.mark_extra_received(extra_id=added.id)
        extras = repo.list_extras_for_month(year_month=ym)
        assert extras[0].received_for_month is True

        repo.unmark_extra_received(extra_id=added.id)
        extras = repo.list_extras_for_month(year_month=ym)
        assert extras[0].received_for_month is False


class TestSQLiteIncomeSourceListActiveForMonth:
    """Test list_active_for_month, applying overrides, skips and received flags."""

    def test_list_active_for_month_basic(self, db) -> None:
        repo = SQLiteIncomeSourceRepository(db.conn)
        repo.add(
            income=IncomeSource(
                id=0,
                name="UC",
                amount=Amount(pence=120000),
                is_reliable=True,
                day_of_month=21,
            )
        )

        sources = repo.list_active_for_month(year_month=YearMonth(2026, 6))

        assert len(sources) == 1
        assert sources[0].name == "UC"
        assert sources[0].skipped_for_month is False
        assert sources[0].has_month_override is False
        assert sources[0].received_for_month is False

    def test_skip_for_month_excludes_income(self, db) -> None:
        repo = SQLiteIncomeSourceRepository(db.conn)
        income = repo.add(
            income=IncomeSource(
                id=0,
                name="Bonus",
                amount=Amount(pence=50000),
                is_reliable=False,
                day_of_month=15,
            )
        )
        ym = YearMonth(2026, 6)

        repo.skip_for_month(income_id=income.id, year_month=ym)

        active = repo.list_active_for_month(year_month=ym)
        assert not any(i.id == income.id for i in active)

        all_sources = repo.list_active_for_month(year_month=ym, include_inactive=True)
        skipped = next(i for i in all_sources if i.id == income.id)
        assert skipped.skipped_for_month is True

    def test_unskip_for_month_restores_income(self, db) -> None:
        repo = SQLiteIncomeSourceRepository(db.conn)
        income = repo.add(
            income=IncomeSource(
                id=0,
                name="Bonus",
                amount=Amount(pence=50000),
                is_reliable=False,
                day_of_month=15,
            )
        )
        ym = YearMonth(2026, 6)

        repo.skip_for_month(income_id=income.id, year_month=ym)
        repo.unskip_for_month(income_id=income.id, year_month=ym)

        active = repo.list_active_for_month(year_month=ym)
        assert any(i.id == income.id for i in active)

    def test_mark_and_unmark_received_for_month(self, db) -> None:
        repo = SQLiteIncomeSourceRepository(db.conn)
        income = repo.add(
            income=IncomeSource(
                id=0,
                name="UC",
                amount=Amount(pence=120000),
                is_reliable=True,
                day_of_month=21,
            )
        )
        ym = YearMonth(2026, 6)

        repo.mark_received_for_month(income_id=income.id, year_month=ym)
        active = repo.list_active_for_month(year_month=ym)
        assert active[0].received_for_month is True

        repo.unmark_received_for_month(income_id=income.id, year_month=ym)
        active = repo.list_active_for_month(year_month=ym)
        assert active[0].received_for_month is False

    def test_hard_delete_cleans_up_month_tables(self, db) -> None:
        repo = SQLiteIncomeSourceRepository(db.conn)
        income = repo.add(
            income=IncomeSource(
                id=0,
                name="UC",
                amount=Amount(pence=120000),
                is_reliable=True,
                day_of_month=21,
            )
        )
        ym = YearMonth(2026, 6)
        repo.skip_for_month(income_id=income.id, year_month=ym)
        repo.mark_received_for_month(income_id=income.id, year_month=ym)

        repo.hard_delete(income_id=income.id)

        cursor = db.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM income_month_skips WHERE income_id = ?",
            (income.id,),
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT COUNT(*) FROM income_month_received WHERE income_id = ?",
            (income.id,),
        )
        assert cursor.fetchone()[0] == 0
