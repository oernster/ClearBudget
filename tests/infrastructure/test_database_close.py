"""Closing a database always closes it, whatever the tidy-up does.

`close()` is what the composition root calls before replacing a budget file
and again as the application exits. It used to run the WAL checkpoint
unguarded, so a locked table raised and the method returned having NEVER
closed the connection.

Two consequences, both seen for real. The file stayed locked for the life of
the process, so replacing it afterwards operated on a database something was
still holding. And the error escaped into the caller: at application exit
that is a process which does not shut down cleanly while still holding the
single-instance lock, so the next launch is refused as "already running" and
the application cannot be started again at all.

The doubles here are hand written; the suite uses no mock library.
"""

from __future__ import annotations

import sqlite3

from clear_budget.infrastructure.sqlite.database import Database


class FakeConnection:
    """A connection whose tidy-up misbehaves in a chosen way."""

    def __init__(self, *, in_transaction: bool = False, execute_raises=None) -> None:
        self.in_transaction = in_transaction
        self._execute_raises = execute_raises
        self.rolled_back = False
        self.closed = False
        self.executed: list[str] = []

    def rollback(self) -> None:
        self.rolled_back = True
        self.in_transaction = False

    def execute(self, sql: str):
        self.executed.append(sql)
        if self._execute_raises is not None:
            raise self._execute_raises
        return None

    def close(self) -> None:
        self.closed = True


def _database_holding(conn: FakeConnection) -> Database:
    database = Database.__new__(Database)
    database.db_path = None
    database.conn = conn
    return database


class TestCloseAlwaysCloses:
    def test_a_checkpoint_that_raises_still_closes_the_connection(self):
        """The exact failure: a locked table left the handle open."""
        conn = FakeConnection(
            execute_raises=sqlite3.OperationalError("database table is locked")
        )

        _database_holding(conn).close()

        assert conn.closed, (
            "close() returned without closing the connection, so the file "
            "stays locked for the life of the process"
        )

    def test_a_checkpoint_that_raises_does_not_propagate(self):
        """At application exit this is a process that never shuts down."""
        conn = FakeConnection(execute_raises=sqlite3.OperationalError("locked"))
        _database_holding(conn).close()  # must not raise

    def test_an_in_flight_transaction_is_rolled_back_before_the_checkpoint(self):
        """An open write blocks the checkpoint, so it is ended first."""
        conn = FakeConnection(in_transaction=True)

        _database_holding(conn).close()

        assert conn.rolled_back
        assert conn.executed == ["PRAGMA wal_checkpoint(RESTART)"]
        assert conn.closed

    def test_nothing_is_rolled_back_when_no_transaction_is_open(self):
        conn = FakeConnection(in_transaction=False)

        _database_holding(conn).close()

        assert not conn.rolled_back
        assert conn.closed

    def test_closing_without_a_connection_is_a_no_op(self):
        database = Database.__new__(Database)
        database.db_path = None
        database.conn = None
        database.close()  # must not raise


class TestARealDatabaseClosesCleanly:
    def test_a_real_connection_with_a_write_in_flight_closes(self, tmp_path):
        database = Database(tmp_path / "real.db")
        database.connect()
        database.create_schema()
        database.conn.execute(
            "INSERT INTO payment_methods (name, type) VALUES ('scratch', 'bank')"
        )
        assert database.conn.in_transaction

        database.close()

        # A closed connection refuses further work, which is the proof.
        try:
            database.conn.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            return
        raise AssertionError("the connection was still usable after close()")
