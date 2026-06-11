"""Uninstall operation."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir

from installer.ops.errors import AppRunningError, InstallerOperationError
from installer.ops.running_app import is_app_running
from installer.ops.shortcuts import get_shortcut_paths, remove_shortcut
from installer.state.registry import (
    delete_uninstall_entry,
    read_uninstall_entry,
    try_read_install_location,
)
from clear_budget.version import APP_AUTHOR, APP_NAME, LEGACY_APP_NAME


@dataclass(frozen=True, slots=True)
class UninstallOptions:
    remove_user_data: bool = True


def uninstall(identity, opts: UninstallOptions) -> None:  # noqa: ANN001 (identity)
    if os.name != "nt":
        raise InstallerOperationError("Uninstall is Windows-only")

    entry = read_uninstall_entry(identity.uninstall_key)
    install_dir = None
    if entry is not None:
        install_dir = entry.install_location
    else:
        install_dir = try_read_install_location(identity.uninstall_key)

    if install_dir is None:
        raise InstallerOperationError(
            "Clear Budget is not detected as installed for this user"
        )

    install_dir = install_dir.resolve()
    exe = install_dir / "ClearBudget.exe"
    if exe.exists() and is_app_running(exe):
        raise AppRunningError("Clear Budget is currently running")

    # Remove shortcuts.
    sp = get_shortcut_paths(identity)
    # If we can't read persisted flags, remove both best-effort.
    if entry is None or entry.shortcut_desktop is not False:
        remove_shortcut(sp.desktop_lnk)
    if entry is None or entry.shortcut_start_menu is not False:
        remove_shortcut(sp.start_menu_lnk)

    # Remove registry first (best effort).
    try:
        delete_uninstall_entry(identity.uninstall_key)
    except Exception:
        pass

    # Remove user data (current and legacy app-name dirs).
    if opts.remove_user_data:
        for name in (APP_NAME, LEGACY_APP_NAME):
            shutil.rmtree(user_data_dir(name, APP_AUTHOR), ignore_errors=True)
            shutil.rmtree(user_cache_dir(name, APP_AUTHOR), ignore_errors=True)

    # Remove install directory.
    _schedule_delete_after_exit(install_dir)


def uninstall_with_feedback(
    identity,
    opts: UninstallOptions,
    *,
    progress=None,
    cancel_event=None,
) -> None:  # noqa: ANN001
    if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
        raise InstallerOperationError("Cancelled")
    if progress:
        progress("Reading installation metadata...")
    uninstall(identity, opts)
    if progress:
        progress("Uninstall scheduled. Closing...")


def _schedule_delete_after_exit(install_dir: Path) -> None:
    """Schedule deletion of install_dir after this process exits.

    If uninstall is invoked from the installed installer copy, Windows will lock
    the running exe. Deleting the whole install directory is therefore done by a
    detached background process.
    """

    install_dir = install_dir.resolve()

    # Use PowerShell with a hidden window.
    # Avoid cmd.exe because it can flash a console window.
    escaped = str(install_dir).replace("'", "''")
    ps = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-WindowStyle",
        "Hidden",
        "-Command",
        (
            "Start-Sleep -Seconds 2; "
            f"Remove-Item -LiteralPath '{escaped}' -Recurse -Force "
            "-ErrorAction SilentlyContinue"
        ),
    ]

    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    subprocess.Popen(  # noqa: S603
        ps,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=create_no_window | subprocess.DETACHED_PROCESS,
    )
