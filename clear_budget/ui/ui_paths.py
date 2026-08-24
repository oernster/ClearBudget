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


def default_data_dir() -> Path:
    """Return the app's own data directory for this operating system.

    Where a saved or loaded budget defaults to, rather than Downloads.
    Downloads is where files go that are LEAVING the machine (a viewer
    package, an exported graph, a backup zip to keep elsewhere); a database
    saved out of the app and loaded back into it never goes anywhere, so it
    belongs beside the data it is a copy of.

    Resolved through `Config`, so it honours the same rules the running app
    does: the redirect a test or a probe sets, plus the preference for the
    legacy directory for as long as one is still there.
    """
    from clear_budget.shared.config import Config

    return Config.app_dir()
