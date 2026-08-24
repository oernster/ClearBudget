"""Migration for installs created under the previous app name.

The app was briefly called "Clear Budget" and is called "ClearBudget" again.
Each rename changed the default install directory and the per-user data and
cache directory names, so an install made under the spaced spelling keeps its
settings in directories the current name never looks at. The helper here
moves that per-user data forward.

It does NOT remove the old install directory; see the note at the foot of
this module for why that codepath is never coming back.

British spelling is used in comments.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir

from clear_budget.version import APP_AUTHOR, APP_NAME, LEGACY_APP_NAME
from installer.constants import ENV_LOCALAPPDATA, LOCAL_APPDATA_FALLBACK

logger = logging.getLogger("installer.install")


def local_appdata_root() -> Path:
    """Return the per-user Local AppData root (``%LOCALAPPDATA%``)."""
    local = os.getenv(ENV_LOCALAPPDATA)
    if local:
        return Path(local)
    return Path.home().joinpath(*LOCAL_APPDATA_FALLBACK)


def migrate_legacy_appdata_dirs() -> None:
    """Move the per-user data and cache dirs from the old app name.

    Older installs stored installer preferences and cache under the previous
    display name. When the new-named directory does not exist yet but the old
    one does, move it so existing settings carry over.

    Best effort per directory: a move that fails leaves the application to
    start with fresh defaults, which is a lost preference and not a reason to
    fail an install.
    """
    for dir_func in (user_data_dir, user_cache_dir):
        try:
            old_dir = Path(dir_func(LEGACY_APP_NAME, APP_AUTHOR)).resolve()
            new_dir = Path(dir_func(APP_NAME, APP_AUTHOR)).resolve()
            if old_dir.exists() and not new_dir.exists():
                new_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_dir), str(new_dir))
        except (OSError, shutil.Error):
            logger.exception("Failed migrating legacy app data dir")


# There is deliberately NO cleanup of `%LOCALAPPDATA%\ClearBudget` here any
# more. A cleanup_orphaned_legacy_install helper used to rmtree that path as
# the pre-rename INSTALL directory; the application's DATA directory then
# moved to exactly that path (5.1) and the next setup run deleted live user
# data believing it was an orphaned install. The stale-install tidy-up was
# never worth a codepath that can delete a directory it does not own; a
# leftover pre-rename install is harmless and the user can remove it by
# hand. tests/structural/test_data_dir_isolation.py now forbids the
# installer from naming that directory at all.
