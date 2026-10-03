"""A new account never adopts a budget file already lying under its name.

Measured: after a restore removed `carol`, her budget stayed on disk; a new,
different `carol` then opened the old one's private figures. Account creation
now moves any such file to the quarantine folder first.
"""

from __future__ import annotations

import sqlite3

import pytest

from clear_budget.auth.user_store import UserStore
from clear_budget.shared.budget_files import QUARANTINE_DIR_NAME
from tests.auth.backup_helpers import marker_of, real_budget_db


@pytest.fixture()
def store(tmp_path):
    s = UserStore(tmp_path / "users.db")
    yield s
    s.close()


def _quarantined(tmp_path):
    root = tmp_path / QUARANTINE_DIR_NAME
    if not root.exists():
        return []
    return sorted(p.name for folder in root.iterdir() for p in folder.iterdir())


def test_a_leftover_budget_is_quarantined_not_adopted(store, tmp_path):
    real_budget_db(tmp_path / "budget_carol.db", marker="CAROL-PRIVATE")
    real_budget_db(tmp_path / "budget_carol__trip.db")
    (tmp_path / "budget_carol.db-journal").write_bytes(b"j")
    (tmp_path / "budgets_carol.json").write_text("{}", encoding="utf-8")

    store.create_user("Carol", "password-1")

    assert not (tmp_path / "budget_carol.db").exists()
    assert _quarantined(tmp_path) == [
        "budget_carol.db",
        "budget_carol.db-journal",
        "budget_carol__trip.db",
        "budgets_carol.json",
    ]
    folder = next((tmp_path / QUARANTINE_DIR_NAME).iterdir())
    assert marker_of(folder / "budget_carol.db") == "CAROL-PRIVATE"


def test_another_live_accounts_files_are_never_moved(store, tmp_path):
    """An account created before separator names were refused keeps its file.

    `alice  bob` can no longer be created, so it is inserted as an older
    version would have left it. Its first budget's name also fits a named
    budget of a new `alice`; the file is the live account's, so it stays.
    """
    store._conn.execute(
        "INSERT INTO users (username, password_hash, recovery_code_hash)"
        " VALUES ('alice  bob', 'x', 'x')"
    )
    store._conn.commit()
    shared_name = tmp_path / "budget_alice__bob.db"
    real_budget_db(shared_name, marker="ALICE-BOB")

    store.create_user("alice", "password-1")

    assert marker_of(shared_name) == "ALICE-BOB"
    assert _quarantined(tmp_path) == []


def test_a_refused_name_moves_nothing(store, tmp_path):
    store.create_user("dave", "password-1")
    real_budget_db(tmp_path / "budget_dave.db", marker="DAVE")
    with pytest.raises(sqlite3.IntegrityError):
        store.create_user("Dave", "password-2")
    assert marker_of(tmp_path / "budget_dave.db") == "DAVE"


def test_a_failed_move_creates_no_account(store, tmp_path, monkeypatch):
    real_budget_db(tmp_path / "budget_erin.db")
    from clear_budget.shared import budget_files

    def refuse(*args, **kwargs):
        raise OSError("in use")

    monkeypatch.setattr(budget_files, "quarantine", refuse)
    with pytest.raises(OSError):
        store.create_user("erin", "password-1")
    assert store.find_user("erin") is None
    assert (tmp_path / "budget_erin.db").exists()
