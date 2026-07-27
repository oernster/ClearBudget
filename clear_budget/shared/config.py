"""Application configuration and paths.

Every path into the user's data (both databases, the logs and the saved theme)
is derived HERE and nowhere else, from one function that an environment
variable can redirect. The variable is not a feature of the app, which never
sets it: it exists so that anything running outside the app (a probe, a script,
the test suite) can be pointed at a scratch directory.

That seam is not decoration. The real directory holds live user data, and a
tool that writes into it silently changes what the user sees at the next
launch: an offscreen probe that applied the light theme in order to measure it
persisted that choice into `ui_settings.json`, and the app duly opened in light
mode afterwards. It looked like a defaulting bug and was not one. Constrain the
bad state rather than remember to avoid it.
"""

import os
from dataclasses import dataclass
from pathlib import Path

_APP_DIR_NAME = ".clearbudget"

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
        """Create config for a specific user's budget database."""
        app_data = _resolve_app_dir()
        safe_name = _safe_username(username)
        return cls(
            db_path=app_data / f"budget_{safe_name}.db",
            log_dir=app_data / "logs",
        )

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
