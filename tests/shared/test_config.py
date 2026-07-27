"""Tests for Config."""

from pathlib import Path

import pytest

from clear_budget.shared.config import APP_DIR_ENV_VAR, Config, _safe_username


class TestConfigDefault:
    """Test Config.default()."""

    def test_default_config(self) -> None:
        """Test creating default config."""
        cfg = Config.default()
        assert cfg.db_path.parent.name == ".clearbudget"
        assert cfg.log_dir.parent.name == ".clearbudget"

    def test_ensure_directories(self, tmp_path) -> None:
        """Test ensure_directories() creates paths."""
        cfg = Config(
            db_path=tmp_path / "clearbudget" / "test.db",
            log_dir=tmp_path / "clearbudget" / "logs",
        )
        cfg.ensure_directories()
        assert cfg.db_path.parent.exists()
        assert cfg.log_dir.exists()


class TestConfigForUser:
    """Test Config.for_user()."""

    def test_for_user_produces_distinct_db_path(self) -> None:
        cfg_alice = Config.for_user("alice")
        cfg_bob = Config.for_user("bob")
        assert cfg_alice.db_path != cfg_bob.db_path

    def test_for_user_filename_contains_username(self) -> None:
        cfg = Config.for_user("alice")
        assert "alice" in cfg.db_path.name

    def test_for_user_parent_is_app_dir(self) -> None:
        cfg = Config.for_user("alice")
        assert cfg.db_path.parent.name == ".clearbudget"

    def test_for_user_default_differs_from_per_user(self) -> None:
        assert Config.default().db_path != Config.for_user("alice").db_path


class TestConfigUsersDatabasePath:
    """Test Config.users_db_path()."""

    def test_users_db_in_app_dir(self) -> None:
        p = Config.users_db_path()
        assert p.name == "users.db"
        assert p.parent.name == ".clearbudget"


class TestConfigAppDir:
    """Test Config.app_dir()."""

    def test_app_dir_is_clearbudget_folder(self, real_app_dir) -> None:
        d = Config.app_dir()
        assert d.name == ".clearbudget"
        assert d.parent == Path.home()


class TestConfigAppDirOverride:
    """The CLEARBUDGET_HOME redirect.

    It exists so that anything running outside the app (a probe, a script, this
    suite) writes to a scratch directory instead of the user's live data. The
    app never sets it.
    """

    def test_an_override_redirects_every_path(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv(APP_DIR_ENV_VAR, str(tmp_path))
        assert Config.app_dir() == tmp_path
        assert Config.users_db_path().parent == tmp_path
        assert Config.for_user("alice").db_path.parent == tmp_path
        assert Config.default().db_path.parent == tmp_path

    def test_no_override_uses_the_real_directory(self, real_app_dir) -> None:
        assert Config.app_dir() == Path.home() / ".clearbudget"

    @pytest.mark.parametrize("blank", ["", "   ", "\t"])
    def test_a_blank_override_is_ignored(self, blank, monkeypatch) -> None:
        """An empty variable means unset, not "write to the current directory"."""
        monkeypatch.setenv(APP_DIR_ENV_VAR, blank)
        assert Config.app_dir() == Path.home() / ".clearbudget"

    def test_the_override_is_read_at_call_time(self, tmp_path, monkeypatch) -> None:
        """Not cached at import, or a test could never redirect it."""
        first = Config.app_dir()
        monkeypatch.setenv(APP_DIR_ENV_VAR, str(tmp_path / "elsewhere"))
        assert Config.app_dir() != first


class TestSafeUsername:
    """Test _safe_username helper."""

    def test_alphanumeric_unchanged(self) -> None:
        assert _safe_username("alice123") == "alice123"

    def test_uppercase_lowercased(self) -> None:
        assert _safe_username("Alice") == "alice"

    def test_spaces_replaced(self) -> None:
        assert _safe_username("John Doe") == "john_doe"

    def test_special_chars_replaced(self) -> None:
        result = _safe_username("user@domain.com")
        assert "@" not in result
        assert "." not in result
