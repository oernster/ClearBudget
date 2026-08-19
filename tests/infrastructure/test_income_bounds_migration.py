"""Upgrading a database that predates the income month bounds changes nothing.

The columns are added NULL on every existing row; a NULL bound reads as
unbounded on that side. So an income that has been appearing in every month
carries on appearing in every month after the upgrade. Anything else would be
the migration itself rewriting history, which is the exact fault the feature
exists to remove.

This builds the OLD table shape by hand rather than trusting the current
baseline DDL, because the baseline already carries the columns and would prove
nothing about an upgrade.
"""

import sqlite3
from dataclasses import replace

import pytest

from clear_budget.infrastructure.sqlite._migrations import apply_pending
from clear_budget.infrastructure.sqlite._schema import create_schema
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.domain.value_objects.year_month import YearMonth

_OLD_INCOME_TABLE = """
    CREATE TABLE income_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        amount_pence INTEGER NOT NULL,
        is_reliable INTEGER NOT NULL,
        day_of_month INTEGER,
        active INTEGER DEFAULT 1
    )
"""

_BOUND_COLUMNS = ("start_year", "start_month", "end_year", "end_month")


@pytest.fixture
def upgraded(tmp_path):
    """A database built on the pre-bounds table shape, then migrated."""
    conn = sqlite3.connect(tmp_path / "old.db")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE income_sources")
    cursor.execute(_OLD_INCOME_TABLE)
    cursor.execute(
        "INSERT INTO income_sources (name, amount_pence, is_reliable, day_of_month)"
        " VALUES ('Universal Credit', 122400, 1, 21)"
    )
    cursor.execute("UPDATE schema_version SET version = 0")
    apply_pending(cursor)
    conn.commit()
    yield conn
    conn.close()


def _columns(conn) -> set[str]:
    return {row[1] for row in conn.execute("PRAGMA table_info(income_sources)")}


class TestTheUpgrade:
    def test_it_adds_the_four_bound_columns(self, upgraded):
        assert set(_BOUND_COLUMNS) <= _columns(upgraded)

    def test_the_existing_row_is_left_unbounded(self, upgraded):
        row = upgraded.execute("SELECT * FROM income_sources").fetchone()
        assert [row[column] for column in _BOUND_COLUMNS] == [None, None, None, None]


class TestBehaviourIsUnchanged:
    def test_the_migrated_income_still_appears_in_every_month(self, upgraded):
        repo = SQLiteIncomeSourceRepository(upgraded)
        for year, month in ((2020, 1), (2026, 6), (2030, 12)):
            listed = repo.list_active_for_month(year_month=YearMonth(year, month))
            assert [i.name for i in listed] == ["Universal Credit"]

    def test_the_migrated_income_reads_back_with_no_bounds(self, upgraded):
        repo = SQLiteIncomeSourceRepository(upgraded)
        income = repo.list_all()[0]
        assert income.start_ym is None
        assert income.end_ym is None

    def test_an_end_month_can_then_be_set_on_the_migrated_row(self, upgraded):
        """The upgrade leaves the row usable, not merely present."""
        repo = SQLiteIncomeSourceRepository(upgraded)
        june = YearMonth(2026, 6)
        repo.update(income=replace(repo.list_all()[0], end_ym=june))
        assert repo.list_all()[0].end_ym == june
        assert repo.list_active_for_month(year_month=june) != []
        assert repo.list_active_for_month(year_month=YearMonth(2026, 7)) == []
