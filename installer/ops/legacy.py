"""Migration/cleanup for installs created under the previous app name.

The app was renamed from "ClearBudget" to "Clear Budget". That rename changed
both the default install directory and the per-user data/cache directory names,
so a fresh install of the renamed app can leave the pre-rename install (and its
data) behind. The helpers here migrate the old per-user data forward and remove
the orphaned old install directory.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir

from clear_budget.version import APP_AUTHOR, APP_NAME, LEGACY_APP_NAME

logger = logging.getLogger("installer.install")


def local_appdata_root() -> Path:
    """Return the per-user Local AppData root (``%LOCALAPPDATA%``)."""

    local = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local)


def migrate_legacy_appdata_dirs() -> None:
    """Move per-user data/cache dirs from the old "ClearBudget" app name.

    Older installs stored installer preferences/cache under the previous display
    name. If the new-named dir doesn't exist yet but the old one does, move it so
    existing settings carry over.
    """

    for dir_func in (user_data_dir, user_cache_dir):
        try:
            old_dir = Path(dir_func(LEGACY_APP_NAME, APP_AUTHOR)).resolve()
            new_dir = Path(dir_func(APP_NAME, APP_AUTHOR)).resolve()
            if old_dir.exists() and not new_dir.exists():
                new_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_dir), str(new_dir))
        except Exception:
            # Best-effort: the app can still run with fresh defaults.
            logger.exception("Failed migrating legacy app data dir")


def cleanup_orphaned_legacy_install(target_dir: Path) -> None:
    """Remove the orphaned legacy-named install directory, if present.

    Renaming the app from "ClearBudget" to "Clear Budget" also moved the default
    install directory from ``%LOCALAPPDATA%\\ClearBudget`` to
    ``%LOCALAPPDATA%\\Clear Budget``. The uninstall registry key, Start Menu
    folder, and shortcut name are all unchanged, so once a new-named install
    exists they point at it and the old directory is left behind as an
    unreferenced orphan. Remove that directory so installing the renamed app
    cleans up the pre-rename install.

    Only the stale install directory is touched. Per-user data/cache dirs are
    handled by :func:`migrate_legacy_appdata_dirs`, and the (shared) Start Menu
    folder still points at the active install, so neither is removed here.
    """

    try:
        legacy_dir = (local_appdata_root() / LEGACY_APP_NAME).resolve()
        target_dir = target_dir.resolve()

        # Never remove the directory we just installed into (e.g. an in-place
        # upgrade where the user kept the legacy path).
        if legacy_dir == target_dir or not legacy_dir.is_dir():
            return

        # Don't remove the directory hosting the currently running installer exe;
        # Windows would lock it and leave a half-deleted install behind.
        running = Path(sys.executable).resolve()
        if running == legacy_dir or legacy_dir in running.parents:
            return

        logger.info("Removing orphaned legacy install directory %s", legacy_dir)
        shutil.rmtree(legacy_dir, ignore_errors=True)
    except Exception:
        # Best-effort: a leftover legacy directory does not affect the new install.
        logger.exception("Failed removing orphaned legacy install directory")
