"""Structural guards on the user's data directory.

`~/.clearbudget` holds live user data: both databases, the logs and the saved
theme. Writing into it from outside the running app changes what the user sees
at their next launch; a settings write is silent, so it surfaces later as a
bug report against the app. It has happened: an offscreen probe applied the
light theme in order to measure it, `apply_theme` persisted that choice; the
app opened in light mode from then on. Nothing was wrong with the app.

Three rules, each with its own failure it is here to catch:

  * the suite never resolves the real directory, so no test can write there
    even by accident (catches the autouse redirect being removed or broken);
  * only `shared/config.py` derives the directory, so the redirect cannot be
    bypassed by a module building the path for itself (catches a new bypass);
  * the theme, the specific thing that got clobbered, lands in the redirected
    directory (catches the seam being real but unused on that path).
"""

import re
from pathlib import Path

import pytest

from clear_budget.shared.config import APP_DIR_ENV_VAR, Config
from clear_budget.ui import theme
from clear_budget.ui.theme_tokens import THEME_DARK, THEME_LIGHT

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_PACKAGE_ROOT = _PROJECT_ROOT / "clear_budget"

# The one module allowed to derive the data directory.
_CONFIG_MODULE = Path("clear_budget") / "shared" / "config.py"

# `Path.home()` is also the Downloads fallback, which is a different concern
# and not a path into user data. Named here so the allowance is deliberate
# rather than a hole in the pattern.
_HOME_ALLOWED = {_CONFIG_MODULE, Path("clear_budget") / "ui" / "ui_paths.py"}

_APP_DIR_LITERAL = re.compile(r"""["']\.clearbudget["']""")
_HOME_CALL = re.compile(r"Path\.home\(\)")
# The platform data roots: a module reading these is deriving the data
# directory for itself, the same bypass as naming `.clearbudget`.
_DATA_ROOT_ENV = re.compile(r"LOCALAPPDATA|XDG_DATA_HOME")


def _platform_real_dir() -> Path:
    """The platform-conventional directory, derived independently here."""
    import os
    import sys

    if sys.platform == "win32":
        base = (os.environ.get("LOCALAPPDATA") or "").strip()
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "ClearBudget"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ClearBudget"
    xdg = (os.environ.get("XDG_DATA_HOME") or "").strip()
    root = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return root / "clearbudget"


def _package_sources():
    for path in _PACKAGE_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path.relative_to(_PROJECT_ROOT), path.read_text(encoding="utf-8")


class TestTheSuiteCannotTouchRealUserData:
    """The autouse redirect in conftest is load-bearing; prove it is on."""

    def _real_candidates(self) -> list[Path]:
        """Both places real data can live: legacy and platform-conventional."""
        return [Path.home() / ".clearbudget", _platform_real_dir()]

    def test_app_dir_is_not_the_real_one(self):
        assert Config.app_dir() not in self._real_candidates()

    def test_every_path_lands_outside_the_real_one(self):
        paths = [
            Config.app_dir(),
            Config.users_db_path(),
            Config.for_user("oliver").db_path,
            Config.for_user("oliver").log_dir,
            Config.default().db_path,
            Config.default().log_dir,
        ]
        inside = [
            p
            for p in paths
            for real in self._real_candidates()
            if real in p.parents or p == real
        ]
        assert not inside, "Test paths resolve inside real user data:\n" + "\n".join(
            str(p) for p in inside
        )

    def test_the_redirect_is_what_puts_them_there(self, isolate_app_dir):
        """Not merely different: specifically the scratch dir conftest set."""
        assert Config.app_dir() == isolate_app_dir

    def test_the_real_path_is_restored_when_the_override_is_cleared(self, real_app_dir):
        """The guard is the env var, not a permanent rewrite of the paths.

        The expectation replicates the resolution rule independently: the
        legacy directory while it exists (its disappearance is the
        migration's completion signal), else the platform directory.
        """
        legacy = Path.home() / ".clearbudget"
        expected = legacy if legacy.is_dir() else _platform_real_dir()
        assert Config.app_dir() == expected


class TestOnlyConfigDerivesTheDataDirectory:
    """A module that builds the path itself would bypass the redirect."""

    def test_no_other_module_names_the_data_directory(self):
        offenders = [
            str(rel)
            for rel, source in _package_sources()
            if rel != _CONFIG_MODULE and _APP_DIR_LITERAL.search(source)
        ]
        assert not offenders, (
            "The '.clearbudget' directory name is derived outside "
            f"{_CONFIG_MODULE}, which bypasses {APP_DIR_ENV_VAR}:\n"
            + "\n".join(offenders)
        )

    def test_no_other_module_reads_the_home_directory(self):
        offenders = [
            str(rel)
            for rel, source in _package_sources()
            if rel not in _HOME_ALLOWED and _HOME_CALL.search(source)
        ]
        assert (
            not offenders
        ), "Path.home() is read outside the modules allowed to:\n" + "\n".join(
            offenders
        )

    def test_no_other_module_reads_the_platform_data_roots(self):
        """LOCALAPPDATA and XDG_DATA_HOME are config.py's business alone."""
        offenders = [
            str(rel)
            for rel, source in _package_sources()
            if rel != _CONFIG_MODULE and _DATA_ROOT_ENV.search(source)
        ]
        assert not offenders, (
            "A platform data root is derived outside "
            f"{_CONFIG_MODULE}, which bypasses {APP_DIR_ENV_VAR}:\n"
            + "\n".join(offenders)
        )


# The startup sequence moved out of main.py when main.py reached the size cap;
# the guard follows the code rather than being retired with it.
_STARTUP_MODULE = "clear_budget/ui/startup.py"


class TestTheMigrationRunsFirstAtStartup:
    """Startup must migrate before the lock and never under the override.

    The single-instance lock file lives in the data directory on macOS and
    Linux, so locking first would lock the directory about to move; and a
    redirected run (the suite, a probe) must never touch real data.
    """

    def test_startup_migrates_before_the_lock_and_behind_the_override(self):
        source = (_PROJECT_ROOT / _STARTUP_MODULE).read_text(encoding="utf-8")
        migrate_at = source.find("migrate_legacy_data(")
        # Matched on the assignment rather than on the callee's name, so
        # moving the lock into its own module (as it has been, to
        # clear_budget.shared.single_instance) cannot silently retire the
        # ordering guard along with the old literal.
        lock_at = source.find("lock = ")
        assert migrate_at != -1, "startup never calls migrate_legacy_data"
        assert lock_at != -1, "startup lost the single-instance lock"
        assert migrate_at < lock_at, (
            "startup acquires the single-instance lock BEFORE migrating, "
            "which locks the directory about to move"
        )
        guard_at = source.find("APP_DIR_ENV_VAR")
        assert guard_at != -1 and guard_at < migrate_at, (
            "startup migrates without checking the override, so a "
            "redirected run would move real user data"
        )

    def test_main_still_starts_through_that_sequence(self):
        """The ordering above is worthless if main stops calling it."""
        source = (_PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
        assert "startup.begin()" in source


class TestTheInstallerLeavesUserDataAlone:
    """Installing, repairing or reinstalling must not disturb the saved theme.

    The rule is that the installer has no business naming the app's data
    directory at all: it lays down program files and it does not know what is
    in `~/.clearbudget`. If a future change reaches in there (to "clean up" or
    to seed a default), a reinstall could silently reset a setting the user
    chose, which is the same failure as the probe that prompted these guards.

    The staging directories the installer creates alongside the INSTALL
    location are a different thing and are named `.clearbudget_staging.<uuid>`,
    which this deliberately does not match.
    """

    def test_no_installer_module_names_the_data_directory(self):
        installer_root = _PROJECT_ROOT / "installer"
        offenders = [
            str(path.relative_to(_PROJECT_ROOT))
            for path in installer_root.rglob("*.py")
            if "__pycache__" not in path.parts
            and _APP_DIR_LITERAL.search(path.read_text(encoding="utf-8"))
        ]
        assert (
            not offenders
        ), "The installer references the app's data directory:\n" + "\n".join(offenders)

    def test_no_installer_module_builds_the_platform_data_directory(self):
        """`%LOCALAPPDATA%\\ClearBudget` is the app's DATA directory (5.1).

        The installer once joined its Local AppData root to the pre-rename
        app name to remove an "orphaned old install"; after the data
        directory moved to exactly that path, one setup run deleted live
        user data. This is the expression that did it; it must never come
        back in any spelling.

        APP_NAME is in the alternation because the app is called
        "ClearBudget" again: the constant now HOLDS the data directory's
        name, so joining the AppData root to it rebuilds the exact path that
        was destroyed, without the literal ever appearing in the source.
        """
        pattern = re.compile(
            r"local_appdata_root\(\)\s*/\s*"
            r"(?:LEGACY_APP_NAME|APP_NAME|[\"']ClearBudget[\"'])"
        )
        installer_root = _PROJECT_ROOT / "installer"
        offenders = [
            str(path.relative_to(_PROJECT_ROOT))
            for path in installer_root.rglob("*.py")
            if "__pycache__" not in path.parts
            and pattern.search(path.read_text(encoding="utf-8"))
        ]
        assert not offenders, (
            "The installer joins its AppData root to the app's data-directory "
            "name, the exact expression that deleted user data:\n"
            + "\n".join(offenders)
        )


class TestTheSavedThemeStaysInTheScratchDirectory:
    """The exact write that clobbered a real setting."""

    @pytest.mark.parametrize("saved", [THEME_DARK, THEME_LIGHT])
    def test_saving_a_theme_writes_only_under_the_redirect(
        self, isolate_app_dir, saved
    ):
        theme._save_theme(saved)
        written = isolate_app_dir / "ui_settings.json"
        assert written.exists()
        assert theme.load_saved_theme() == saved

    def test_the_real_settings_file_is_never_the_target(self):
        real = Path.home() / ".clearbudget" / "ui_settings.json"
        assert Config.app_dir() / "ui_settings.json" != real
