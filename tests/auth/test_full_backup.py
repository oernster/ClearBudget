"""Tests for the full backup: accounts plus every budget in one zip."""

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
from clear_budget.infrastructure.sqlite.database import Database


def _real_users_db(path, username: str = "oliver") -> None:
    store = UserStore(path)
    store.create_user(username, "a-password-12345", is_admin=True)
    store.close()


def _real_budget_db(path) -> None:
    db = Database(path)
    db.connect()
    db.create_schema()
    db.close()


def _data_dir(tmp_path):
    app_dir = tmp_path / "data"
    app_dir.mkdir()
    _real_users_db(app_dir / USERS_DB_NAME)
    _real_budget_db(app_dir / "budget_oliver.db")
    _real_budget_db(app_dir / "budget_oliver__household.db")
    (app_dir / "budgets_oliver.json").write_text("{}", encoding="utf-8")
    (app_dir / "ui_settings.json").write_text("{}", encoding="utf-8")
    (app_dir / "arrows").mkdir()
    (app_dir / "arrows" / "up.png").write_bytes(b"\x89PNG")
    return app_dir


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
        original_users = (app_dir / USERS_DB_NAME).read_bytes()
        # Wreck the live files, then restore over them.
        (app_dir / USERS_DB_NAME).unlink()
        _real_users_db(app_dir / USERS_DB_NAME, username="someone_else")
        (app_dir / "budgets_oliver.json").write_text("wrecked", encoding="utf-8")
        names = restore_full_backup(package_path=dest, app_dir=app_dir)
        assert USERS_DB_NAME in names
        assert (app_dir / USERS_DB_NAME).read_bytes() == original_users
        assert (app_dir / "budgets_oliver.json").read_text(encoding="utf-8") == "{}"
        assert not (app_dir / "_restore_staging").exists()

    def test_files_not_in_the_backup_survive(self, tmp_path):
        app_dir = _data_dir(tmp_path)
        dest = tmp_path / "backup.zip"
        create_full_backup(app_dir=app_dir, dest_path=dest)
        _real_budget_db(app_dir / "budget_newuser.db")
        restore_full_backup(package_path=dest, app_dir=app_dir)
        assert (app_dir / "budget_newuser.db").exists()
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
