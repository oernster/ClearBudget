"""Installer logging setup.

The setup program logs to a per-user location so a failure in the field can be
diagnosed from the log rather than from a window that has already closed. The
directory comes from an environment variable, so the test suite redirects it
into a temporary tree. British spelling is used in comments.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from installer.constants import (
    ENV_LOCALAPPDATA,
    INSTALLER_DIR_NAME,
    INSTALLER_LOG_DIR_NAME,
    INSTALLER_LOG_NAME,
    LOCAL_APPDATA_FALLBACK,
)

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_READY_MESSAGE = "Installer logging initialized"


def installer_log_dir() -> Path:
    local = os.getenv(ENV_LOCALAPPDATA)
    root = Path(local) if local else Path.home().joinpath(*LOCAL_APPDATA_FALLBACK)
    return root / INSTALLER_DIR_NAME / INSTALLER_LOG_DIR_NAME


def installer_log_path() -> Path:
    return installer_log_dir() / INSTALLER_LOG_NAME


def setup_installer_logging() -> Path:
    """Configure root logging and return the log file path."""
    log_dir = installer_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = installer_log_path()

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[logging.FileHandler(log_path, encoding="utf-8")],
    )

    logging.getLogger("installer").info(_READY_MESSAGE)
    return log_path
