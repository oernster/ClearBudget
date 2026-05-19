"""Tests for SQLite Database class."""

import sqlite3

import pytest

from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.database import Database


class TestDatabaseConnection:
    """Test database connection."""

    def test_connect_creates_connection(self, tmp_path) -> None:
        """Test connecting to database."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)

        conn = db.connect()

        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        # Verify row_factory is set
        assert db.conn.row_factory == sqlite3.Row
        db.close()

    def test_close_closes_connection(self, tmp_path) -> None:
        """Test closing database connection."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.connect()

        db.close()

        # Trying to use the closed connection should raise
        with pytest.raises(sqlite3.ProgrammingError):
            db.conn.execute("SELECT 1")

    def test_create_schema_without_connection(self, tmp_path) -> None:
        """Test that create_schema raises if not connected."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)

        with pytest.raises(RuntimeError, match="Not connected"):
            db.create_schema()

    def test_get_or_create_month_without_connection(self, tmp_path) -> None:
        """Test that get_or_create_month raises if not connected."""
        db_path = tmp_path / "test.db"
        db = Database(db_path)

        with pytest.raises(RuntimeError, match="Not connected"):
            db.get_or_create_month(year_month=YearMonth(2026, 6))


class TestDatabaseSchema:
    """Test database schema creation."""

    def test_create_schema(self, db) -> None:
        """Test that schema is created successfully."""
        cursor = db.conn.cursor()

        # Check that tables exist
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        assert "bills" in tables
        assert "income_sources" in tables
        assert "months" in tables
        assert "month_bills" in tables
        assert "month_income" in tables
        assert "credit_cards" in tables
        assert "payment_methods" in tables


class TestDatabaseGetOrCreateMonth:
    """Test get_or_create_month method."""

    def test_get_or_create_creates_new_month(self, db) -> None:
        """Test creating a new month."""
        month_id = db.get_or_create_month(year_month=YearMonth(2026, 6))

        assert month_id > 0

        # Verify it was created
        cursor = db.conn.cursor()
        cursor.execute("SELECT year, month FROM months WHERE id = ?", (month_id,))
        row = cursor.fetchone()

        assert row["year"] == 2026
        assert row["month"] == 6

    def test_get_or_create_returns_existing_month(self, db) -> None:
        """Test getting an existing month."""
        month_id_1 = db.get_or_create_month(year_month=YearMonth(2026, 6))
        month_id_2 = db.get_or_create_month(year_month=YearMonth(2026, 6))

        assert month_id_1 == month_id_2

    def test_get_or_create_different_months(self, db) -> None:
        """Test creating different months."""
        month_id_1 = db.get_or_create_month(year_month=YearMonth(2026, 6))
        month_id_2 = db.get_or_create_month(year_month=YearMonth(2026, 7))

        assert month_id_1 != month_id_2

    def test_create_schema_idempotent(self, tmp_path) -> None:
        """Calling create_schema twice hits the except branches for existing columns."""
        db_path = tmp_path / "idempotent.db"
        database = Database(db_path)
        database.connect()
        database.create_schema()  # first call adds columns
        database.create_schema()  # second call hits except: pass for each ALTER TABLE
        database.close()
