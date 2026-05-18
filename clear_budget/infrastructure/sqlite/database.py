"""SQLite database setup and schema."""

import sqlite3
from pathlib import Path

from clear_budget.domain.value_objects.year_month import YearMonth


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

    def _migrate_credit_cards_schema(self, cursor) -> None:
        """Add new columns to credit_cards table if they don't exist."""
        columns_to_add = [
            ("interest_rate_apr", "REAL DEFAULT NULL"),
            ("payment_due_day", "INTEGER DEFAULT 1"),
            ("card_expiry_month", "INTEGER DEFAULT NULL"),
            ("card_expiry_year", "INTEGER DEFAULT NULL"),
            ("minimum_payment_pence", "INTEGER DEFAULT NULL"),
            ("active", "INTEGER DEFAULT 1"),
        ]

        for col_name, col_def in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE credit_cards ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass

    def create_schema(self) -> None:
        """Create database schema and run migrations."""
        if not self.conn:
            raise RuntimeError("Not connected to database")

        cursor = self.conn.cursor()

        # Payment methods table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Ensure bank account exists with id=1
        cursor.execute(
            """
            INSERT OR IGNORE INTO payment_methods (id, name, type)
            VALUES (1, 'Bank Account', 'bank')
            """
        )

        # Bill templates table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                amount_pence INTEGER NOT NULL,
                payment_method_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                bill_type TEXT NOT NULL,
                day_of_month INTEGER,
                start_year INTEGER NOT NULL,
                start_month INTEGER NOT NULL,
                end_year INTEGER,
                end_month INTEGER,
                active INTEGER DEFAULT 1,
                FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id)
            )
            """
        )

        # Income sources table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS income_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                amount_pence INTEGER NOT NULL,
                is_reliable INTEGER NOT NULL,
                day_of_month INTEGER,
                active INTEGER DEFAULT 1
            )
            """
        )

        # Months table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS months (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(year, month)
            )
            """
        )

        # Month bills table (instantiated bills for specific months)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS month_bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month_id INTEGER NOT NULL,
                bill_template_id INTEGER,
                name TEXT NOT NULL,
                amount_pence INTEGER NOT NULL,
                payment_method_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                day_of_month INTEGER,
                is_ad_hoc INTEGER DEFAULT 0,
                FOREIGN KEY (month_id) REFERENCES months(id),
                FOREIGN KEY (bill_template_id) REFERENCES bills(id),
                FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id)
            )
            """
        )

        # Month income table (instantiated income for specific months)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS month_income (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month_id INTEGER NOT NULL,
                income_source_id INTEGER,
                name TEXT NOT NULL,
                amount_pence INTEGER NOT NULL,
                is_reliable INTEGER NOT NULL,
                day_of_month INTEGER,
                FOREIGN KEY (month_id) REFERENCES months(id),
                FOREIGN KEY (income_source_id) REFERENCES income_sources(id)
            )
            """
        )

        # Credit cards table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS credit_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                credit_limit_pence INTEGER NOT NULL,
                current_balance_used_pence INTEGER NOT NULL DEFAULT 0,
                interest_rate_apr REAL DEFAULT NULL,
                payment_due_day INTEGER DEFAULT 1,
                card_expiry_month INTEGER DEFAULT NULL,
                card_expiry_year INTEGER DEFAULT NULL,
                minimum_payment_pence INTEGER DEFAULT NULL,
                active INTEGER DEFAULT 1
            )
            """
        )

        # Migrations: add columns to credit_cards if they don't exist (for existing databases)
        self._migrate_credit_cards_schema(cursor)

        # Settings table (for app configuration)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        self.conn.commit()

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
