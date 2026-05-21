"""Application configuration and paths."""

from dataclasses import dataclass
from pathlib import Path

_APP_DIR_NAME = ".clearbudget"


@dataclass(frozen=True, slots=True)
class Config:
    """Application configuration."""

    db_path: Path
    log_dir: Path

    @classmethod
    def default(cls) -> "Config":
        """Create default config using standard paths (legacy single-user budget)."""
        app_data = Path.home() / _APP_DIR_NAME
        return cls(
            db_path=app_data / "budget.db",
            log_dir=app_data / "logs",
        )

    @classmethod
    def for_user(cls, username: str) -> "Config":
        """Create config for a specific user's budget database."""
        app_data = Path.home() / _APP_DIR_NAME
        safe_name = _safe_username(username)
        return cls(
            db_path=app_data / f"budget_{safe_name}.db",
            log_dir=app_data / "logs",
        )

    @staticmethod
    def users_db_path() -> Path:
        """Path to the central users authentication database."""
        return Path.home() / _APP_DIR_NAME / "users.db"

    @staticmethod
    def app_dir() -> Path:
        return Path.home() / _APP_DIR_NAME

    def ensure_directories(self) -> None:
        """Ensure all directories exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


def _safe_username(username: str) -> str:
    """Convert username to a filesystem-safe string."""
    import re

    return re.sub(r"[^a-zA-Z0-9_-]", "_", username).lower()
