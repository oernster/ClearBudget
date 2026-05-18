"""Application configuration and paths."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Config:
    """Application configuration."""

    db_path: Path
    log_dir: Path

    @classmethod
    def default(cls) -> "Config":
        """Create default config using standard XDG paths."""
        home = Path.home()
        app_data = home / ".clearbudget"

        return cls(
            db_path=app_data / "budget.db",
            log_dir=app_data / "logs",
        )

    def ensure_directories(self) -> None:
        """Ensure all directories exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
