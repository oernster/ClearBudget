"""Tests for Config."""

import os
from pathlib import Path

import pytest

from clear_budget.shared.config import (
    APP_DIR_ENV_VAR,
    Config,
    _choose_app_dir,
    _platform_app_dir,
    _safe_username,
)


def _expected_real_dir() -> Path:
    """The real directory, derived INDEPENDENTLY of the code under test.

    The resolution rule prefers the legacy directory while it exists (its
    disappearance is the migration's completion signal), so the expectation
    depends on this machine's state; replicating the rule here keeps the
    test true before and after the machine migrates.
    """
    import sys

    legacy = Path.home() / ".clearbudget"
    if legacy.is_dir():
        return legacy
    if sys.platform == "win32":
        base = (os.environ.get("LOCALAPPDATA") or "").strip()
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "ClearBudget"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ClearBudget"
    xdg = (os.environ.get("XDG_DATA_HOME") or "").strip()
    root = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return root / "clearbudget"


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

    def test_app_dir_follows_the_resolution_rule(self, real_app_dir) -> None:
        assert Config.app_dir() == _expected_real_dir()


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
        assert Config.app_dir() == _expected_real_dir()

    @pytest.mark.parametrize("blank", ["", "   ", "\t"])
    def test_a_blank_override_is_ignored(self, blank, monkeypatch) -> None:
        """An empty variable means unset, not "write to the current directory"."""
        monkeypatch.setenv(APP_DIR_ENV_VAR, blank)
        assert Config.app_dir() == _expected_real_dir()

    def test_the_override_is_read_at_call_time(self, tmp_path, monkeypatch) -> None:
        """Not cached at import; otherwise a test could never redirect it."""
        first = Config.app_dir()
        monkeypatch.setenv(APP_DIR_ENV_VAR, str(tmp_path / "elsewhere"))
        assert Config.app_dir() != first


class TestPlatformAppDir:
    """Every platform branch of the conventional-directory rule."""

    def test_windows_uses_localappdata(self) -> None:
        d = _platform_app_dir(platform="win32", env={"LOCALAPPDATA": r"C:\LAD"})
        assert d == Path(r"C:\LAD") / "ClearBudget"

    @pytest.mark.parametrize("env", [{}, {"LOCALAPPDATA": "   "}])
    def test_windows_falls_back_when_localappdata_is_absent(self, env) -> None:
        d = _platform_app_dir(platform="win32", env=env)
        assert d == Path.home() / "AppData" / "Local" / "ClearBudget"

    def test_macos_uses_application_support(self) -> None:
        d = _platform_app_dir(platform="darwin", env={})
        assert d == Path.home() / "Library" / "Application Support" / "ClearBudget"

    def test_linux_honours_xdg_data_home(self, tmp_path) -> None:
        d = _platform_app_dir(platform="linux", env={"XDG_DATA_HOME": str(tmp_path)})
        assert d == tmp_path / "clearbudget"

    @pytest.mark.parametrize("env", [{}, {"XDG_DATA_HOME": "   "}])
    def test_linux_defaults_to_local_share(self, env) -> None:
        d = _platform_app_dir(platform="linux", env=env)
        assert d == Path.home() / ".local" / "share" / "clearbudget"

    def test_defaults_read_the_running_platform(self) -> None:
        assert _platform_app_dir() == _platform_app_dir(platform=None, env=None)


class TestChooseAppDir:
    """The resolution rule: override, then a still-present legacy, then new."""

    def test_the_override_wins_outright(self, tmp_path) -> None:
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        chosen = _choose_app_dir(
            override=str(tmp_path / "override"),
            legacy=legacy,
            platform_dir=tmp_path / "platform",
        )
        assert chosen == tmp_path / "override"

    def test_a_surviving_legacy_directory_is_preferred(self, tmp_path) -> None:
        """Its disappearance is the migration's completion signal, so a failed
        move keeps the app on the data it always had."""
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        chosen = _choose_app_dir(
            override="", legacy=legacy, platform_dir=tmp_path / "platform"
        )
        assert chosen == legacy

    def test_no_legacy_means_the_platform_directory(self, tmp_path) -> None:
        chosen = _choose_app_dir(
            override="",
            legacy=tmp_path / "gone",
            platform_dir=tmp_path / "platform",
        )
        assert chosen == tmp_path / "platform"


class TestConfigMigrationPaths:
    """The two paths the startup migration is handed."""

    def test_legacy_app_dir_is_the_dot_directory(self) -> None:
        assert Config.legacy_app_dir() == Path.home() / ".clearbudget"

    def test_platform_app_dir_ignores_the_legacy_preference(self) -> None:
        assert Config.platform_app_dir() == _platform_app_dir()


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
