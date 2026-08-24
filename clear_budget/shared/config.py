"""Application configuration and paths.

Every path into the user's data (both databases, the logs and the saved theme)
is derived HERE and nowhere else, from one function that an environment
variable can redirect. The variable is not a feature of the app, which never
sets it: it exists so that anything running outside the app (a probe, a script,
the test suite) can be pointed at a scratch directory.

That seam is not decoration. The real directory holds live user data; a
tool that writes into it silently changes what the user sees at the next
launch: an offscreen probe that applied the light theme in order to measure it
persisted that choice into `ui_settings.json`; the app duly opened in light
mode afterwards. It looked like a defaulting bug and was not one. Constrain the
bad state rather than remember to avoid it.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

# The pre-5.1 data directory. Kept only so existing installs migrate and so a
# failed migration leaves the app running on the data it always had.
_LEGACY_APP_DIR_NAME = ".clearbudget"

# The platform-conventional directory names. Windows and macOS app-data
# folders are conventionally branded; XDG directories are lower-case.
_BRANDED_DIR_NAME = "ClearBudget"
_XDG_DIR_NAME = "clearbudget"

# The slug of a user's FIRST budget. Reserved and never allocated to a named
# one, because it is what maps to the pre-named-budgets `budget_<user>.db`.
LEGACY_BUDGET_SLUG = ""

# Redirects the data directory. Read at call time, never cached, so a test or a
# probe can set it after import.
APP_DIR_ENV_VAR = "CLEARBUDGET_HOME"


def _legacy_app_dir() -> Path:
    """The pre-5.1 data directory (`~/.clearbudget`)."""
    return Path.home() / _LEGACY_APP_DIR_NAME


def _platform_app_dir(*, platform: str | None = None, env=None) -> Path:
    """The platform-conventional data directory.

    `platform` and `env` are injectable so every branch is testable without
    faking `sys.platform`; the app always passes neither.
    """
    platform = platform or sys.platform
    env = os.environ if env is None else env
    if platform == "win32":
        base = (env.get("LOCALAPPDATA") or "").strip()
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / _BRANDED_DIR_NAME
    if platform == "darwin":
        return Path.home() / "Library" / "Application Support" / _BRANDED_DIR_NAME
    xdg = (env.get("XDG_DATA_HOME") or "").strip()
    root = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return root / _XDG_DIR_NAME


def _choose_app_dir(*, override: str, legacy: Path, platform_dir: Path) -> Path:
    """The resolution rule, pure so every branch is testable with tmp paths.

    The override wins outright. Otherwise the LEGACY directory is preferred
    for as long as it exists: its disappearance is the migration's completion
    signal, so an interrupted move leaves the app running on the data it
    always had and the retry happens at the next launch. Only when nothing
    legacy remains does the platform-conventional directory take over.
    """
    text = override.strip()
    if text:
        return Path(text)
    if legacy.is_dir():
        return legacy
    return platform_dir


def _resolve_app_dir() -> Path:
    """The data directory: the override when set and non-blank, else the real one."""
    return _choose_app_dir(
        override=os.environ.get(APP_DIR_ENV_VAR, ""),
        legacy=_legacy_app_dir(),
        platform_dir=_platform_app_dir(),
    )


@dataclass(frozen=True, slots=True)
class Config:
    """Application configuration."""

    db_path: Path
    log_dir: Path

    @classmethod
    def default(cls) -> "Config":
        """Create default config using standard paths (legacy single-user budget)."""
        app_data = _resolve_app_dir()
        return cls(
            db_path=app_data / "budget.db",
            log_dir=app_data / "logs",
        )

    @classmethod
    def for_user(cls, username: str) -> "Config":
        """Create config for a user's FIRST budget database.

        This is the legacy single-budget path and stays exactly what it always
        was, so an install that predates named budgets opens the same file it
        always did. It is `for_user_budget` with the reserved empty slug.
        """
        return cls.for_user_budget(username, LEGACY_BUDGET_SLUG)

    @classmethod
    def for_user_budget(cls, username: str, slug: str) -> "Config":
        """Create config for one named budget belonging to `username`.

        The empty slug is RESERVED for the user's first budget and maps to the
        unsuffixed `budget_<user>.db`. Every later budget carries its slug
        after a double underscore, which cannot occur in a slug itself because
        a slug never contains an underscore run (see `safe_slug`).
        """
        app_data = _resolve_app_dir()
        safe_name = _safe_username(username)
        suffix = f"__{slug}" if slug else ""
        return cls(
            db_path=app_data / f"budget_{safe_name}{suffix}.db",
            log_dir=app_data / "logs",
        )

    @staticmethod
    def budgets_index_path(username: str) -> Path:
        """Path to the sidecar listing `username`'s budgets and the active one."""
        return _resolve_app_dir() / f"budgets_{_safe_username(username)}.json"

    @staticmethod
    def users_db_path() -> Path:
        """Path to the central users authentication database."""
        return _resolve_app_dir() / "users.db"

    @staticmethod
    def app_dir() -> Path:
        return _resolve_app_dir()

    @staticmethod
    def legacy_app_dir() -> Path:
        """The pre-5.1 data directory, named only for the startup migration."""
        return _legacy_app_dir()

    @staticmethod
    def platform_app_dir() -> Path:
        """The migration's TARGET: the platform directory, ignoring the
        legacy-preference rule that `app_dir` applies while `~/.clearbudget`
        still exists."""
        return _platform_app_dir()

    def ensure_directories(self) -> None:
        """Ensure all directories exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


def _safe_username(username: str) -> str:
    """Convert username to a filesystem-safe string."""
    import re

    return re.sub(r"[^a-zA-Z0-9_-]", "_", username).lower()
