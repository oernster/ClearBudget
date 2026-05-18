"""Helpers for locating embedded resources.

When bundled with PyInstaller, files added via --add-data are unpacked under
sys._MEIPASS.
"""

from __future__ import annotations

import sys
from pathlib import Path


def bundled_data_root() -> Path:
    """Return the directory where bundled data files are available."""

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)

    # Running from source.
    return Path(__file__).resolve().parents[2]


def resource_path(relative_path: str) -> Path:
    """Resolve a resource path relative to the bundle data root."""

    return bundled_data_root() / relative_path
