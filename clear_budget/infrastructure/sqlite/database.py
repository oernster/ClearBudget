"""SQLite database setup and schema."""

import sqlite3
from pathlib import Path

from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite._schema import (
    create_schema as _create_schema,
)


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: Path) -> None:
        """Initialize database with path."""
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Connect to database."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self) -> None:
        """Close the connection, leaving the file complete on disk.

        Closing has to succeed. It is what the composition root does before
        replacing a database; a close that raises part way leaves the
        connection open on a file about to be swapped, which is how a budget
        gets destroyed.

        Two things could raise here and both are handled rather than hoped
        against. An uncommitted transaction blocks the checkpoint, so it is
        rolled back first: SQLite discards it on close anyway, so this only
        makes the existing outcome explicit and early. And a checkpoint that
        still cannot run (another connection reading, perhaps no WAL at all)
        is not a reason to leave the connection open, so the close proceeds.
        """
        if not self.conn:
            return
        try:
            if self.conn.in_transaction:
                self.conn.rollback()
            self.conn.execute("PRAGMA wal_checkpoint(RESTART)")
        except sqlite3.Error:
            pass
        finally:
            self.conn.close()

    def create_schema(self) -> None:
        """Create database schema and run migrations."""
        if not self.conn:
            raise RuntimeError("Not connected to database")
        _create_schema(self.conn)

    def get_or_create_month(self, year_month: YearMonth) -> int:
        """Get or create a month record, return its ID."""
        if not self.conn:
            raise RuntimeError("Not connected to database")

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM months WHERE year = ? AND month = ?",
            (year_month.year, year_month.month),
        )
        row = cursor.fetchone()

        if row:
            return row["id"]

        cursor.execute(
            "INSERT INTO months (year, month) VALUES (?, ?)",
            (year_month.year, year_month.month),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_bank_balance_pence(self) -> int:  # pragma: no cover
        """Get stored bank account balance in pence."""
        if not self.conn:  # pragma: no cover
            raise RuntimeError("Not connected to database")

        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", ("bank_balance",))
        row = cursor.fetchone()
        return int(row["value"]) if row else 0

    def set_bank_balance_pence(self, pence: int) -> None:  # pragma: no cover
        """Set bank account balance in pence."""
        if not self.conn:  # pragma: no cover
            raise RuntimeError("Not connected to database")

        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("bank_balance", str(pence)),
        )
        self.conn.commit()
