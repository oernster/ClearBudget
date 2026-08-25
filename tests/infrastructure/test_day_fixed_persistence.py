"""The day-fixed flag survives storage and arrives on upgraded databases.

The flag records the exception (a date that cannot be moved), so the round
trip matters in both directions: a True must come back True and every row
written before the concept existed must read False, the honest default for
data that never stated otherwise.
"""

import sqlite3
from dataclasses import replace

import pytest

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite._migrations import apply_pending
from clear_budget.infrastructure.sqlite._schema import create_schema
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)


def _bill(*, day_fixed: bool = False) -> Bill:
    return Bill(
        id=0,
        name="Rent",
        amount=Amount(pence=80000),
        payment_method_id=1,
        category="housing",
        bill_type="fixed",
        day_of_month=10,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
        target_card_id=None,
        day_fixed=day_fixed,
    )


def _income(*, day_fixed: bool = False) -> IncomeSource:
    return IncomeSource(
        id=0,
        name="Universal Credit",
        amount=Amount(pence=122400),
        is_reliable=True,
        day_of_month=20,
        day_fixed=day_fixed,
    )


class TestBillRoundTrip:
    def test_defaults_to_movable(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        added = repo.add(bill=_bill())
        assert repo.get_by_id(bill_id=added.id).day_fixed is False

    def test_a_fixed_day_comes_back_fixed(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        added = repo.add(bill=_bill(day_fixed=True))
        assert repo.get_by_id(bill_id=added.id).day_fixed is True

    def test_update_flips_the_flag(self, db) -> None:
        repo = SQLiteBillRepository(db.conn)
        added = repo.add(bill=_bill())
        repo.update(bill=replace(added, day_fixed=True))
        assert repo.get_by_id(bill_id=added.id).day_fixed is True


class TestIncomeRoundTrip:
    def test_defaults_to_movable(self, db) -> None:
        repo = SQLiteIncomeSourceRepository(db.conn)
        added = repo.add(income=_income())
        assert repo.get_by_id(income_id=added.id).day_fixed is False

    def test_a_fixed_day_comes_back_fixed(self, db) -> None:
        repo = SQLiteIncomeSourceRepository(db.conn)
        added = repo.add(income=_income(day_fixed=True))
        assert repo.get_by_id(income_id=added.id).day_fixed is True

    def test_update_flips_the_flag(self, db) -> None:
        repo = SQLiteIncomeSourceRepository(db.conn)
        added = repo.add(income=_income())
        repo.update(income=replace(added, day_fixed=True))
        assert repo.get_by_id(income_id=added.id).day_fixed is True


@pytest.fixture
def upgraded(tmp_path):
    """A database whose tables predate the flag, then migrated.

    The pre-flag shape is produced by dropping the columns from the current
    baseline rather than hand-writing the old DDL: what the upgrade must
    handle is exactly "these tables, without these columns".
    """
    conn = sqlite3.connect(tmp_path / "old.db")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE bills DROP COLUMN day_fixed")
    cursor.execute("ALTER TABLE income_sources DROP COLUMN day_fixed")
    cursor.execute(
        "INSERT INTO bills (name, amount_pence, payment_method_id, category,"
        " bill_type, day_of_month, start_year, start_month) VALUES"
        " ('Rent', 80000, 1, 'housing', 'fixed', 10, 2026, 1)"
    )
    cursor.execute(
        "INSERT INTO income_sources (name, amount_pence, is_reliable,"
        " day_of_month) VALUES ('Universal Credit', 122400, 1, 20)"
    )
    cursor.execute("UPDATE schema_version SET version = 0")
    apply_pending(cursor)
    conn.commit()
    yield conn
    conn.close()


class TestTheUpgrade:
    def test_existing_rows_read_as_movable(self, upgraded) -> None:
        bill_repo = SQLiteBillRepository(upgraded)
        income_repo = SQLiteIncomeSourceRepository(upgraded)
        (bill,) = bill_repo.list_active_for_month(year_month=YearMonth(2026, 8))
        assert bill.day_fixed is False
        (income,) = income_repo.list_active()
        assert income.day_fixed is False
