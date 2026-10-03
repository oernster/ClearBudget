"""Validation reads the data, not just the schema.

Measured: a budget whose `settings` page was overwritten behind an intact
schema passed `validate_db`, replaced a good budget through Restore and through
Load, then failed to open with "database disk image is malformed".
"""

from __future__ import annotations

import sqlite3

from clear_budget.auth.user_store import UserStore
from clear_budget.shared.db_validation import validate_accounts_db, validate_db
from tests.auth.backup_helpers import real_budget_db, wreck_table_page


def test_a_budget_with_a_damaged_data_page_is_refused(tmp_path):
    good = tmp_path / "good.db"
    real_budget_db(good, marker="M")
    damaged = tmp_path / "damaged.db"
    damaged.write_bytes(wreck_table_page(good, "settings"))
    assert validate_db(good) is None
    error = validate_db(damaged)
    assert error is not None
    assert "damaged" in error


class TestTheAccountsDatabase:
    def test_a_real_accounts_store_passes(self, tmp_path):
        path = tmp_path / "users.db"
        store = UserStore(path)
        store.create_user("alice", "password-1")
        store.close()
        assert validate_accounts_db(path) is None

    def test_no_users_table(self, tmp_path):
        path = tmp_path / "users.db"
        real_budget_db(path)
        assert "no users table" in validate_accounts_db(path)

    def test_a_users_table_of_the_wrong_shape(self, tmp_path):
        path = tmp_path / "users.db"
        conn = sqlite3.connect(str(path))
        conn.execute("CREATE TABLE users (x)")
        conn.commit()
        conn.close()
        error = validate_accounts_db(path)
        assert "missing columns" in error
        assert "password_hash" in error

    def test_damaged_data(self, tmp_path):
        good = tmp_path / "good.db"
        store = UserStore(good)
        store.create_user("alice", "password-1")
        store.close()
        path = tmp_path / "users.db"
        path.write_bytes(wreck_table_page(good, "users"))
        assert "damaged" in validate_accounts_db(path)

    def test_not_a_database(self, tmp_path):
        path = tmp_path / "users.db"
        path.write_bytes(b"not sqlite at all, not even close")
        assert "not readable" in validate_accounts_db(path)

    def test_an_absent_file(self, tmp_path):
        assert "not readable" in validate_accounts_db(tmp_path / "absent.db")
