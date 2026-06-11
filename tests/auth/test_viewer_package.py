"""Tests for export_viewer_package / import_viewer_package."""

import zipfile
from pathlib import Path

import pytest

from clear_budget.auth.user_store import UserStore
from clear_budget.auth.viewer_package import (
    export_viewer_package,
    import_viewer_package,
)
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.shared.config import Config


@pytest.fixture()
def source_db(tmp_path):
    """A valid ClearBudget database to export."""
    path = tmp_path / "source.db"
    db = Database(path)
    db.connect()
    db.create_schema()
    db.close()
    return path


@pytest.fixture()
def store(tmp_path):
    s = UserStore(tmp_path / "users.db")
    yield s
    s.close()


class TestExportViewerPackage:
    """Test export_viewer_package."""

    def test_creates_zip_with_db_and_account(self, source_db, tmp_path) -> None:
        dest = tmp_path / "package.zip"
        export_viewer_package(source_db, dest, "dad", "viewerpass")
        assert dest.exists()
        with zipfile.ZipFile(dest) as zf:
            names = zf.namelist()
            assert "data.db" in names
            assert "account.json" in names

    def test_account_json_contains_username(self, source_db, tmp_path) -> None:
        dest = tmp_path / "package.zip"
        export_viewer_package(source_db, dest, "dad", "viewerpass")
        with zipfile.ZipFile(dest) as zf:
            import json

            account = json.loads(zf.read("account.json").decode())
        assert account["username"] == "dad"
        assert "password_hash" in account
        assert "recovery_code_hash" in account


class TestImportViewerPackage:
    """Test import_viewer_package."""

    def test_creates_read_only_account(self, source_db, store, tmp_path) -> None:
        package = tmp_path / "package.zip"
        export_viewer_package(source_db, package, "dad", "viewerpass")

        config = Config(
            db_path=tmp_path / "installed" / "budget_dad.db",
            log_dir=tmp_path / "installed" / "logs",
        )
        user = import_viewer_package(package, store, config=config)

        assert user.username == "dad"
        assert user.is_read_only is True
        assert store.verify_password("dad", "viewerpass") is not None

    def test_installs_database_snapshot(self, source_db, store, tmp_path) -> None:
        package = tmp_path / "package.zip"
        export_viewer_package(source_db, package, "dad", "viewerpass")

        config = Config(
            db_path=tmp_path / "installed" / "budget_dad.db",
            log_dir=tmp_path / "installed" / "logs",
        )
        import_viewer_package(package, store, config=config)

        assert config.db_path.exists()

    def test_refresh_updates_existing_account_and_data(
        self, source_db, store, tmp_path
    ) -> None:
        package = tmp_path / "package.zip"
        export_viewer_package(source_db, package, "dad", "firstpass")
        config = Config(
            db_path=tmp_path / "installed" / "budget_dad.db",
            log_dir=tmp_path / "installed" / "logs",
        )
        first = import_viewer_package(package, store, config=config)

        package2 = tmp_path / "package2.zip"
        export_viewer_package(source_db, package2, "dad", "secondpass")
        second = import_viewer_package(package2, store, config=config)

        assert second.id == first.id
        assert store.verify_password("dad", "firstpass") is None
        assert store.verify_password("dad", "secondpass") is not None

    def test_rejects_package_missing_account_entry(self, tmp_path, store) -> None:
        package = tmp_path / "bad.zip"
        with zipfile.ZipFile(package, "w") as zf:
            zf.writestr("data.db", b"not a real db")
        with pytest.raises(ValueError, match="Not a valid viewer package"):
            import_viewer_package(package, store)

    def test_rejects_package_with_invalid_account_json(self, tmp_path, store) -> None:
        package = tmp_path / "bad.zip"
        with zipfile.ZipFile(package, "w") as zf:
            zf.writestr("data.db", b"not a real db")
            zf.writestr("account.json", "not json")
        with pytest.raises(ValueError, match="Not a valid viewer package"):
            import_viewer_package(package, store)

    def test_default_config_derived_from_username(
        self, source_db, store, tmp_path, monkeypatch
    ) -> None:
        """When config is omitted, it defaults to Config.for_user(username)."""
        package = tmp_path / "package.zip"
        export_viewer_package(source_db, package, "viewer_default_cfg", "viewerpass")

        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        user = import_viewer_package(package, store)

        assert user.username == "viewer_default_cfg"
        installed = fake_home / ".clearbudget" / "budget_viewer_default_cfg.db"
        assert installed.exists()

    def test_rejects_invalid_database(self, tmp_path, store) -> None:
        import json

        package = tmp_path / "bad.zip"
        account = {
            "username": "dad",
            "password_hash": UserStore.hash_password("pw"),
            "recovery_code_hash": UserStore.generate_recovery_code()[1],
        }
        with zipfile.ZipFile(package, "w") as zf:
            zf.writestr("data.db", b"not a real sqlite database")
            zf.writestr("account.json", json.dumps(account))

        config = Config(
            db_path=tmp_path / "installed" / "budget_dad.db",
            log_dir=tmp_path / "installed" / "logs",
        )
        with pytest.raises(ValueError):
            import_viewer_package(package, store, config=config)
        assert not config.db_path.exists()
        assert store.find_user("dad") is None
