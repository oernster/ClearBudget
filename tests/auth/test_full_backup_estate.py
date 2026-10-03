"""What a full backup takes from a live estate and what a restore leaves.

Two measured defects. A restore left behind every budget that belonged to an
account the backup does not hold, so a new, different account given the same
name opened the old one's private figures. And Back Up Everything copied the
bytes of databases the app had open, so a write in progress went into the
backup as if it had been committed.
"""

from __future__ import annotations

import sqlite3
import zipfile

import pytest

from clear_budget.auth.full_backup import (
    USERS_DB_NAME,
    FullBackupError,
    create_full_backup,
    restore_full_backup,
)
from clear_budget.auth.user_store import UserStore
from clear_budget.shared import db_copy
from clear_budget.shared.budget_files import QUARANTINE_DIR_NAME
from tests.auth.backup_helpers import (
    data_dir,
    marker_of,
    real_budget_db,
    set_marker,
)


def _restore_after_carol_arrives(tmp_path):
    """Back up, then add carol with a private budget, then restore."""
    app_dir = data_dir(tmp_path)
    package = tmp_path / "full.zip"
    create_full_backup(app_dir=app_dir, dest_path=package)
    store = UserStore(app_dir / USERS_DB_NAME)
    store.create_user("carol", "carol-password-1")
    store.close()
    real_budget_db(app_dir / "budget_carol.db", marker="CAROL-PRIVATE")
    real_budget_db(app_dir / "budget_carol__holiday.db", marker="CAROL-HOLIDAY")
    (app_dir / "budget_carol.db-journal").write_bytes(b"carol journal")
    (app_dir / "budgets_carol.json").write_text("{}", encoding="utf-8")
    result = restore_full_backup(package_path=package, app_dir=app_dir)
    return app_dir, result


class TestAccountsTheBackupDoesNotHold:
    _CAROL = (
        "budget_carol.db",
        "budget_carol.db-journal",
        "budget_carol__holiday.db",
        "budgets_carol.json",
    )

    def test_their_files_move_to_quarantine_and_are_never_deleted(self, tmp_path):
        app_dir, result = _restore_after_carol_arrives(tmp_path)
        for name in self._CAROL:
            assert not (app_dir / name).exists(), f"{name} survived the restore"
        assert result.quarantine_dir is not None
        assert result.quarantine_dir.parent == app_dir / QUARANTINE_DIR_NAME
        assert sorted(result.quarantined) == sorted(self._CAROL)
        assert marker_of(result.quarantine_dir / "budget_carol.db") == ("CAROL-PRIVATE")

    def test_files_of_restored_accounts_and_other_files_stay(self, tmp_path):
        app_dir, _ = _restore_after_carol_arrives(tmp_path)
        assert (app_dir / "budget_oliver.db").exists()
        assert (app_dir / "budget_oliver__household.db").exists()
        assert (app_dir / "budgets_oliver.json").exists()
        assert (app_dir / "ui_settings.json").exists()

    def test_a_new_account_with_the_old_name_starts_empty(self, tmp_path):
        app_dir, _ = _restore_after_carol_arrives(tmp_path)
        store = UserStore(app_dir / USERS_DB_NAME)
        assert store.find_user("carol") is None
        store.create_user("carol", "a-different-person")
        store.close()
        assert not (app_dir / "budget_carol.db").exists()

    def test_a_restore_with_no_orphans_reports_none(self, tmp_path):
        app_dir = data_dir(tmp_path)
        package = tmp_path / "full.zip"
        create_full_backup(app_dir=app_dir, dest_path=package)
        result = restore_full_backup(package_path=package, app_dir=app_dir)
        assert result.quarantined == []
        assert result.quarantine_dir is None
        assert not (app_dir / QUARANTINE_DIR_NAME).exists()

    def test_a_budget_in_the_backup_for_no_account_is_quarantined(self, tmp_path):
        app_dir = data_dir(tmp_path)
        real_budget_db(app_dir / "budget_ghost.db")
        package = tmp_path / "full.zip"
        create_full_backup(app_dir=app_dir, dest_path=package)
        result = restore_full_backup(package_path=package, app_dir=app_dir)
        assert result.quarantined == ["budget_ghost.db"]


class TestBackUpEverythingSnapshotsOpenDatabases:
    def test_a_pending_write_is_not_in_the_backup(self, tmp_path):
        app_dir = data_dir(tmp_path)
        set_marker(app_dir / "budget_oliver.db", "COMMITTED")
        writer = sqlite3.connect(str(app_dir / "budget_oliver.db"))
        writer.execute("UPDATE settings SET value='PENDING' WHERE key='marker'")
        package = tmp_path / "full.zip"
        try:
            create_full_backup(app_dir=app_dir, dest_path=package)
        finally:
            writer.rollback()
            writer.close()
        extracted = tmp_path / "extracted.db"
        with zipfile.ZipFile(package) as zf:
            extracted.write_bytes(zf.read("budget_oliver.db"))
        assert marker_of(extracted) == "COMMITTED"

    def test_a_half_written_database_is_refused_not_copied(self, tmp_path, monkeypatch):
        """The writer has spilled uncommitted pages into the file itself.

        A byte copy took them into the backup as if committed (measured). A
        snapshot cannot read the file at that moment, so the backup is
        refused after a short wait rather than written wrong or hung.
        """
        monkeypatch.setattr(db_copy, "SNAPSHOT_BUSY_TIMEOUT_S", 0.1, raising=False)
        app_dir = data_dir(tmp_path)
        set_marker(app_dir / "budget_oliver.db", "COMMITTED")
        writer = sqlite3.connect(str(app_dir / "budget_oliver.db"))
        writer.execute("PRAGMA cache_size=1")
        writer.execute("BEGIN")
        writer.execute("UPDATE settings SET value='HALF' WHERE key='marker'")
        writer.execute("CREATE TABLE filler (x)")
        writer.executemany(
            "INSERT INTO filler VALUES (?)", [(b"z" * 3000,) for _ in range(200)]
        )
        package = tmp_path / "full.zip"
        try:
            with pytest.raises(FullBackupError, match="budget_oliver.db"):
                create_full_backup(app_dir=app_dir, dest_path=package)
        finally:
            writer.rollback()
            writer.close()
        assert not package.exists()
