"""Tests for Config."""

from pathlib import Path

from clear_budget.shared.config import Config


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
