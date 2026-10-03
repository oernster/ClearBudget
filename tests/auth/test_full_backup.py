"""Tests for the full backup: accounts plus every budget in one zip."""

import pathlib
import zipfile

import pytest

from clear_budget.auth.full_backup import (
    USERS_DB_NAME,
    FullBackupError,
    create_full_backup,
    restore_full_backup,
    validate_full_backup,
)
from clear_budget.auth.user_store import UserStore
from clear_budget.shared.budget_files import QUARANTINE_DIR_NAME
from tests.auth.backup_helpers import data_dir as _data_dir
from tests.auth.backup_helpers import real_budget_db as _real_budget_db
from tests.auth.backup_helpers import real_users_db as _real_users_db


class TestCreate:
    def test_bundles_accounts_budgets_and_sidecars_only(self, tmp_path):
        app_dir = _data_dir(tmp_path)
        dest = tmp_path / "backup.zip"
        names = create_full_backup(app_dir=app_dir, dest_path=dest)
        assert names == [
            USERS_DB_NAME,
            "budget_oliver.db",
            "budget_oliver__household.db",
            "budgets_oliver.json",
        ]
        with zipfile.ZipFile(dest) as zf:
            assert sorted(zf.namelist()) == sorted(names)

    def test_no_accounts_database_refuses(self, tmp_path):
        app_dir = tmp_path / "data"
        app_dir.mkdir()
        with pytest.raises(FullBackupError):
            create_full_backup(app_dir=app_dir, dest_path=tmp_path / "b.zip")


class TestValidate:
    def test_a_created_backup_validates(self, tmp_path):
        app_dir = _data_dir(tmp_path)
        dest = tmp_path / "backup.zip"
        create_full_backup(app_dir=app_dir, dest_path=dest)
        assert USERS_DB_NAME in validate_full_backup(dest)

    def test_not_a_zip_is_refused(self, tmp_path):
        bogus = tmp_path / "backup.zip"
        bogus.write_bytes(b"not a zip at all")
        with pytest.raises(FullBackupError):
            validate_full_backup(bogus)

    def test_a_missing_file_is_refused(self, tmp_path):
        with pytest.raises(FullBackupError):
            validate_full_backup(tmp_path / "absent.zip")

    def test_a_zip_without_the_accounts_database_is_refused(self, tmp_path):
        dest = tmp_path / "backup.zip"
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr("budget_oliver.db", b"x")
        with pytest.raises(FullBackupError):
            validate_full_backup(dest)

    @pytest.mark.parametrize(
        "stray",
        [
            "notes.txt",
            "sub/budget_oliver.db",
            "..\\budget_oliver.db",
            "../users.db",
            "ui_settings.json",
        ],
    )
    def test_a_stray_or_traversing_entry_is_refused(self, tmp_path, stray):
        dest = tmp_path / "backup.zip"
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr(USERS_DB_NAME, b"x")
            zf.writestr(stray, b"y")
        with pytest.raises(FullBackupError):
            validate_full_backup(dest)


class TestRestore:
    def test_round_trip_replaces_the_live_files(self, tmp_path):
        app_dir = _data_dir(tmp_path)
        dest = tmp_path / "backup.zip"
        create_full_backup(app_dir=app_dir, dest_path=dest)
        # Wreck the live files, then restore over them.
        (app_dir / USERS_DB_NAME).unlink()
        _real_users_db(app_dir / USERS_DB_NAME, "someone_else")
        (app_dir / "budgets_oliver.json").write_text("wrecked", encoding="utf-8")
        names = restore_full_backup(package_path=dest, app_dir=app_dir).names
        assert USERS_DB_NAME in names
        # Compared by what sign-in sees: a snapshot taken through SQLite is
        # the same database but not the same bytes (its change counter moves).
        store = UserStore(app_dir / USERS_DB_NAME)
        try:
            assert store.verify_password("oliver", "a-password-12345") is not None
            assert store.find_user("someone_else") is None
        finally:
            store.close()
        assert (app_dir / "budgets_oliver.json").read_text(encoding="utf-8") == "{}"
        assert not (app_dir / "_restore_staging").exists()

    def test_a_budget_of_no_restored_account_is_quarantined_not_kept(self, tmp_path):
        """It used to survive, so a new account of that name inherited it."""
        app_dir = _data_dir(tmp_path)
        dest = tmp_path / "backup.zip"
        create_full_backup(app_dir=app_dir, dest_path=dest)
        _real_budget_db(app_dir / "budget_newuser.db")
        result = restore_full_backup(package_path=dest, app_dir=app_dir)
        assert not (app_dir / "budget_newuser.db").exists()
        assert (result.quarantine_dir / "budget_newuser.db").exists()
        assert result.quarantine_dir.parent.name == QUARANTINE_DIR_NAME
        assert (app_dir / "ui_settings.json").exists()

    def test_a_backup_with_a_broken_accounts_db_changes_nothing(self, tmp_path):
        app_dir = _data_dir(tmp_path)
        live_users = (app_dir / USERS_DB_NAME).read_bytes()
        dest = tmp_path / "backup.zip"
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr(USERS_DB_NAME, b"not sqlite")
        with pytest.raises(FullBackupError):
            restore_full_backup(package_path=dest, app_dir=app_dir)
        assert (app_dir / USERS_DB_NAME).read_bytes() == live_users
        assert not (app_dir / "_restore_staging").exists()

    def test_a_sqlite_file_without_a_users_table_is_refused(self, tmp_path):
        app_dir = _data_dir(tmp_path)
        wrong = tmp_path / "wrong.db"
        _real_budget_db(wrong)  # valid sqlite yet a budget schema
        dest = tmp_path / "backup.zip"
        with zipfile.ZipFile(dest, "w") as zf:
            zf.write(wrong, USERS_DB_NAME)
        with pytest.raises(FullBackupError):
            restore_full_backup(package_path=dest, app_dir=app_dir)

    def test_a_backup_with_a_broken_budget_db_changes_nothing(self, tmp_path):
        app_dir = _data_dir(tmp_path)
        live_budget = (app_dir / "budget_oliver.db").read_bytes()
        dest = tmp_path / "backup.zip"
        with zipfile.ZipFile(dest, "w") as zf:
            zf.write(app_dir / USERS_DB_NAME, USERS_DB_NAME)
            zf.writestr("budget_oliver.db", b"not a database")
        with pytest.raises(FullBackupError):
            restore_full_backup(package_path=dest, app_dir=app_dir)
        assert (app_dir / "budget_oliver.db").read_bytes() == live_budget


class TestARestoreThatFailsPartWayThrough:
    """A half-applied restore is worse than a refused one.

    The files are replaced one at a time and there is no atomic multi-file
    move, so a failure on the second file used to leave the accounts database
    already swapped: every account from the backup paired with every budget
    from before it. Measured, not imagined: one stray read handle on a budget
    was enough to raise PermissionError at exactly that point.
    """

    def test_the_original_files_are_put_back(self, tmp_path, monkeypatch):
        app_dir = _data_dir(tmp_path)
        package = tmp_path / "full.zip"
        create_full_backup(app_dir=app_dir, dest_path=package)

        before = {
            name: (app_dir / name).read_bytes()
            for name in (USERS_DB_NAME, "budget_oliver.db", "budgets_oliver.json")
        }
        # Make the live files distinguishable from the backup's copies.
        for name in before:
            (app_dir / name).write_bytes(before[name] + b"LIVE")
        live_now = {name: (app_dir / name).read_bytes() for name in before}

        real_replace = pathlib.Path.replace

        def flaky(self, target):
            # One budget refuses to move, which is what a stray read handle
            # on Windows looks like. Everything else, the undo included,
            # behaves normally.
            if self.name == "budget_oliver.db":
                raise PermissionError("Access is denied")
            return real_replace(self, target)

        # Scoped: `monkeypatch.undo()` would also lift the conftest redirect.
        with monkeypatch.context() as patch:
            patch.setattr(pathlib.Path, "replace", flaky)
            with pytest.raises(PermissionError):
                restore_full_backup(package_path=package, app_dir=app_dir)

        for name, content in live_now.items():
            assert (
                app_dir / name
            ).read_bytes() == content, (
                f"{name} was left in the backup's state after a failed restore"
            )

    def test_a_budget_the_machine_does_not_have_yet_still_arrives(self, tmp_path):
        """Restoring onto a machine with fewer budgets than the backup holds."""
        source = _data_dir(tmp_path / "source")
        package = tmp_path / "full.zip"
        create_full_backup(app_dir=source, dest_path=package)

        target = tmp_path / "target"
        target.mkdir()
        _real_users_db(target / USERS_DB_NAME)

        restore_full_backup(package_path=package, app_dir=target)

        assert (target / "budget_oliver.db").is_file()
        assert (target / "budget_oliver__household.db").is_file()
