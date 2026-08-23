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
from dataclasses import dataclass
from pathlib import Path

_APP_DIR_NAME = ".clearbudget"

# The slug of a user's FIRST budget. Reserved and never allocated to a named
# one, because it is what maps to the pre-named-budgets `budget_<user>.db`.
LEGACY_BUDGET_SLUG = ""

# Redirects the data directory. Read at call time, never cached, so a test or a
# probe can set it after import.
APP_DIR_ENV_VAR = "CLEARBUDGET_HOME"


def _resolve_app_dir() -> Path:
    """The data directory: the override when set and non-blank, else the real one."""
    override = os.environ.get(APP_DIR_ENV_VAR, "").strip()
    return Path(override) if override else Path.home() / _APP_DIR_NAME


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

    def ensure_directories(self) -> None:
        """Ensure all directories exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


def _safe_username(username: str) -> str:
    """Convert username to a filesystem-safe string."""
    import re

    return re.sub(r"[^a-zA-Z0-9_-]", "_", username).lower()
