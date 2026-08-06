"""The migration engine: ordered, applied once and loud on a real failure."""

import sqlite3

import pytest

from clear_budget.infrastructure.sqlite._migrations import (
    LATEST_VERSION,
    apply_pending,
    read_version,
)
from clear_budget.infrastructure.sqlite._schema import create_schema

_BASELINE = 0


@pytest.fixture
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "budget.db")
    create_schema(connection)
    yield connection
    connection.close()


class TestMigrationVersioning:
    def test_a_new_database_is_taken_to_the_latest_version(self, conn) -> None:
        assert read_version(conn.cursor()) == LATEST_VERSION

    def test_applying_again_changes_nothing(self, conn) -> None:
        assert apply_pending(conn.cursor()) == LATEST_VERSION
        assert apply_pending(conn.cursor()) == LATEST_VERSION

    def test_pending_migrations_run_when_the_version_is_behind(self, conn) -> None:
        """An older database is brought forward rather than left alone."""
        cursor = conn.cursor()
        cursor.execute("UPDATE schema_version SET version = ?", (_BASELINE,))
        assert apply_pending(cursor) == LATEST_VERSION

    def test_version_reads_the_baseline_when_the_row_is_absent(self, conn) -> None:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM schema_version")
        assert read_version(cursor) == _BASELINE


class TestMigrationFailure:
    def test_a_genuine_failure_raises_rather_than_passing_silently(self, conn) -> None:
        """The point of the rewrite.

        The previous mechanism wrapped every `ALTER` in `except Exception: pass`,
        so a missing table, a locked file or a full disk all read as "the column
        is already there" and the application carried on against a schema it had
        never checked. A column that is genuinely present is now established by
        reading `PRAGMA table_info`, so anything else is a real error and escapes.
        """
        cursor = conn.cursor()
        cursor.execute("UPDATE schema_version SET version = ?", (_BASELINE,))
        cursor.execute("DROP TABLE bills")
        with pytest.raises(sqlite3.OperationalError):
            apply_pending(cursor)

    def test_an_already_present_column_is_not_an_error(self, conn) -> None:
        """Re-running every column step against a current database is a no-op."""
        cursor = conn.cursor()
        cursor.execute("UPDATE schema_version SET version = ?", (_BASELINE,))
        assert apply_pending(cursor) == LATEST_VERSION
        assert read_version(cursor) == LATEST_VERSION
