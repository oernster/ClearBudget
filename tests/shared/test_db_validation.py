"""Tests for validate_db and is_accounts_database."""

from clear_budget.auth.user_store import UserStore
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.shared.db_validation import is_accounts_database, validate_db


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


def test_a_file_that_does_not_exist_reports_error(tmp_path) -> None:
    """A read-only connection to an absent file fails before it is opened, so
    the close in the finally block has no connection to work with."""
    error = validate_db(tmp_path / "absent.db")
    assert error is not None
    assert "Not a valid SQLite database" in error


class TestTellingTheAccountsStoreFromABudget:
    """The two files live in one directory, so the Load dialog offers both."""

    def test_the_real_accounts_store_is_recognised(self, tmp_path) -> None:
        path = tmp_path / "users.db"
        store = UserStore(path)
        store.close()
        assert is_accounts_database(path) is True

    def test_a_renamed_copy_of_it_is_still_recognised(self, tmp_path) -> None:
        """Answered from the shape, so renaming it changes nothing."""
        original = tmp_path / "users.db"
        UserStore(original).close()
        disguised = tmp_path / "budget_someone.db"
        disguised.write_bytes(original.read_bytes())
        assert is_accounts_database(disguised) is True

    def test_a_budget_is_not_the_accounts_store(self, tmp_path) -> None:
        path = tmp_path / "budget_someone.db"
        db = Database(path)
        db.connect()
        db.create_schema()
        db.close()
        assert is_accounts_database(path) is False

    def test_an_empty_database_is_neither(self, tmp_path) -> None:
        import sqlite3

        path = tmp_path / "empty.db"
        sqlite3.connect(path).close()
        assert is_accounts_database(path) is False

    def test_a_file_that_is_not_a_database_is_not_the_accounts_store(
        self, tmp_path
    ) -> None:
        """Not this function's question; validate_db answers it properly."""
        path = tmp_path / "not_a_db.db"
        path.write_text("hello world")
        assert is_accounts_database(path) is False

    def test_a_missing_file_is_not_the_accounts_store(self, tmp_path) -> None:
        assert is_accounts_database(tmp_path / "nothing_here.db") is False
