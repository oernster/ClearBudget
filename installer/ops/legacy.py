"""Migration and cleanup for installs created under the previous app name.

The app was renamed from "ClearBudget" to "Clear Budget". That rename changed
both the default install directory and the per-user data and cache directory
names, so a fresh install of the renamed app can leave the pre-rename install
(and its settings) behind. The helpers here migrate the old per-user data
forward and remove the orphaned old install directory.

British spelling is used in comments.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
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


def cleanup_orphaned_legacy_install(target_dir: Path) -> None:
    """Remove the orphaned legacy-named install directory, if present.

    Renaming the app also moved the default install directory. The uninstall
    registry key, the Start Menu folder and the shortcut name are all
    unchanged, so once a new-named install exists they point at it and the old
    directory is left behind as an unreferenced orphan. Removing it means
    installing the renamed app cleans up the pre-rename install.

    Only the stale install directory is touched. Per-user data and cache dirs
    are handled by :func:`migrate_legacy_appdata_dirs`; the Start Menu
    folder still points at the active install, so neither is removed here.
    """
    try:
        legacy_dir = (local_appdata_root() / LEGACY_APP_NAME).resolve()
        target_dir = target_dir.resolve()
    except OSError:  # pragma: no cover
        # Defensive: resolve() does not raise for any path this environment can
        # produce. Doing nothing leaves a stale directory, which is harmless.
        return

    # Never remove the directory just installed into (an in-place upgrade where
    # the user kept the legacy path); never the one hosting the running
    # installer exe, which Windows would lock into a half-deleted state.
    if legacy_dir == target_dir or not legacy_dir.is_dir():
        return
    running = Path(sys.executable).resolve()
    if running == legacy_dir or legacy_dir in running.parents:
        return

    logger.info("Removing orphaned legacy install directory %s", legacy_dir)
    shutil.rmtree(legacy_dir, ignore_errors=True)
