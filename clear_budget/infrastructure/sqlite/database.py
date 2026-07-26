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
        """Close database connection."""
        if self.conn:
            self.conn.execute("PRAGMA wal_checkpoint(RESTART)")
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
