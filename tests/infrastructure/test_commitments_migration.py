"""An existing budget gains the commitments table and changes nothing else.

The guarantee this file exists to hold: upgrading must not restate a single
figure. A database written before reserves existed has no commitments, so the
floor is the emergency buffer on every day, exactly as it was when the buffer
was one number. The projection is left to say so for itself rather than being
taken on trust.
"""

import sqlite3
from datetime import date, timedelta

import pytest

from clear_budget.domain.services.reserve_floor import ReserveFloor
from clear_budget.infrastructure.sqlite._migrations import (
    LATEST_VERSION,
    apply_pending,
    read_version,
)
from clear_budget.infrastructure.sqlite._schema import create_schema
from clear_budget.infrastructure.sqlite.commitment_repository import (
    SQLiteCommitmentRepository,
)
from clear_budget.application.services._settings_operations import (
    get_variable_spend_monthly_pence,
)

_VERSION_BEFORE_COMMITMENTS = 10
BUFFER_PENCE = 15000


@pytest.fixture
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "budget.db")
    connection.row_factory = sqlite3.Row
    create_schema(connection)
    yield connection
    connection.close()


def _table_exists(connection, table: str) -> bool:
    cursor = connection.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    )
    return cursor.fetchone() is not None


class TestTheMigration:
    def test_a_new_database_carries_the_table(self, conn):
        assert _table_exists(conn, "commitments")

    def test_the_version_moved_on(self, conn):
        assert read_version(conn.cursor()) == LATEST_VERSION

    def test_a_database_predating_reserves_gains_the_table(self, tmp_path):
        """The upgrade path a user actually takes."""
        connection = sqlite3.connect(tmp_path / "old.db")
        connection.row_factory = sqlite3.Row
        create_schema(connection)
        cursor = connection.cursor()
        cursor.execute("DROP TABLE commitments")
        cursor.execute(
            "UPDATE schema_version SET version = ?", (_VERSION_BEFORE_COMMITMENTS,)
        )
        connection.commit()
        assert not _table_exists(connection, "commitments")

        apply_pending(connection.cursor())

        assert _table_exists(connection, "commitments")
        assert read_version(connection.cursor()) == LATEST_VERSION
        connection.close()

    def test_applying_it_twice_changes_nothing(self, conn):
        apply_pending(conn.cursor())
        assert read_version(conn.cursor()) == LATEST_VERSION


class TestNothingIsRestated:
    def test_an_upgraded_budget_reserves_nothing(self, conn):
        assert SQLiteCommitmentRepository(conn=conn).list_all() == []

    def test_everyday_spending_starts_unset(self, conn):
        """Unset, never zero: the absence of a claim is not a claim."""
        assert get_variable_spend_monthly_pence(conn) is None

    def test_the_floor_is_the_plain_buffer_on_every_day(self, conn):
        """The whole point of the migration, swept across a year."""
        commitments = tuple(SQLiteCommitmentRepository(conn=conn).list_all())
        floor = ReserveFloor(
            buffer_pence=BUFFER_PENCE,
            commitments=commitments,
            variable_spend_monthly_pence=get_variable_spend_monthly_pence(conn),
        )
        assert floor.is_flat
        day = date(2026, 1, 1)
        while day <= date(2027, 1, 1):
            assert floor.at(day) == BUFFER_PENCE, day
            day += timedelta(days=1)
