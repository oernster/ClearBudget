"""Cross-platform filesystem path helpers for the UI layer."""

from pathlib import Path

from PySide6.QtCore import QStandardPaths


def default_downloads_dir() -> Path:
    """Return the user's Downloads folder on Windows/macOS/Linux.

    Falls back to the user's home directory if the platform does not
    report a Downloads location.
    """
    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DownloadLocation
    )
    if location:
        return Path(location)
    return Path.home()
