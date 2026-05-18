"""Installer logging setup.

We log to a per-user location so failures in the field can be diagnosed.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path


def installer_log_dir() -> Path:
    local = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "ClearBudgetInstaller" / "logs"


def installer_log_path() -> Path:
    return installer_log_dir() / "setup.log"


def setup_installer_logging() -> Path:
    """Configure root logging and return the log file path."""

    log_dir = installer_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = installer_log_path()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8")],
    )

    logging.getLogger("installer").info("Installer logging initialized")
    return log_path
