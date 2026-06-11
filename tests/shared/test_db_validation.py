"""Tests for validate_db."""

from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.shared.db_validation import validate_db


def test_valid_database_returns_none(tmp_path) -> None:
    path = tmp_path / "valid.db"
    db = Database(path)
    db.connect()
    db.create_schema()
    db.close()
    assert validate_db(path) is None


def test_missing_tables_reports_error(tmp_path) -> None:
    import sqlite3

    path = tmp_path / "empty.db"
    sqlite3.connect(path).close()
    error = validate_db(path)
    assert error is not None
    assert "missing tables" in error


def test_missing_columns_reports_error(tmp_path) -> None:
    import sqlite3

    path = tmp_path / "valid.db"
    db = Database(path)
    db.connect()
    db.create_schema()
    db.conn.execute("ALTER TABLE bills RENAME COLUMN active TO was_active")
    db.conn.commit()
    db.close()
    error = validate_db(path)
    assert error is not None
    assert "missing columns" in error


def test_not_a_sqlite_file_reports_error(tmp_path) -> None:
    path = tmp_path / "not_a_db.db"
    path.write_text("hello world")
    error = validate_db(path)
    assert error is not None
    assert "Not a valid SQLite database" in error
