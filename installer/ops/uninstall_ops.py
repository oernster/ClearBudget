"""Uninstall operation."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir

from installer.ops.errors import AppRunningError, InstallerOperationError
from installer.ops.running_app import is_app_running
from installer.ops.shortcuts import (
    get_shortcut_paths,
    remove_shortcut,
    remove_taskbar_pin,
)
from installer.state.registry import (
    delete_uninstall_entry,
    read_uninstall_entry,
    try_read_install_location,
)
from clear_budget.version import APP_AUTHOR, APP_NAME, LEGACY_APP_NAME


# Direct (synchronous) delete: a brief bounded retry rides out transient locks
# (e.g. an anti-virus scanner holding a handle) before the failure is surfaced.
_DIRECT_DELETE_ATTEMPTS = 5
_DIRECT_DELETE_INTERVAL_S = 0.5

# Deferred delete: when the running installer lives inside the target dir it
# cannot remove its own exe, so a detached helper polls until the exiting
# installer releases the lock instead of guessing a single fixed delay.
_DEFERRED_DELETE_ATTEMPTS = 30
_DEFERRED_DELETE_INTERVAL_MS = 500


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

    # Remove the taskbar pin too, so uninstall leaves nothing launchable behind.
    # Always attempted: the pin is user-created and not tracked by the persisted
    # shortcut flags.
    remove_taskbar_pin(sp.taskbar_lnk)

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

    # Remove install directory. When this uninstaller runs from outside the
    # install dir nothing locks it (the app is already confirmed not running),
    # so delete synchronously and surface any failure. Only the installed copy
    # living inside the dir cannot delete its own exe, and so it defers.
    if _running_from_inside(install_dir):
        _schedule_delete_after_exit(install_dir)
    else:
        _delete_install_dir_now(install_dir)


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


def _running_from_inside(install_dir: Path) -> bool:
    """Return True if this process's exe lives inside install_dir.

    Mirrors the guard in :mod:`installer.ops.legacy`: an installer copied into
    the install dir cannot delete its own running exe and so needs the deferred
    path, whereas a standalone installer run from elsewhere has full control.
    On any uncertainty resolving paths, prefer the safe deferred path.
    """

    try:
        running = Path(sys.executable).resolve()
        install_dir = install_dir.resolve()
    except Exception:
        return True
    return running == install_dir or install_dir in running.parents


def _delete_install_dir_now(install_dir: Path) -> None:
    """Delete install_dir synchronously, retrying briefly on transient locks.

    Used when the installer runs from outside install_dir, so removal is fully
    under our control. A failure is raised rather than silently swallowed.
    """

    install_dir = install_dir.resolve()
    last_error: OSError | None = None
    for attempt in range(_DIRECT_DELETE_ATTEMPTS):
        try:
            shutil.rmtree(install_dir)
        except FileNotFoundError:
            return
        except OSError as exc:
            last_error = exc
        if not install_dir.exists():
            return
        if attempt < _DIRECT_DELETE_ATTEMPTS - 1:
            time.sleep(_DIRECT_DELETE_INTERVAL_S)
    raise InstallerOperationError(
        f"Could not remove the install directory at {install_dir}: {last_error}"
    )


def _schedule_delete_after_exit(install_dir: Path) -> None:
    """Schedule deletion of install_dir after this process exits.

    When uninstall is invoked from the installer copy living inside install_dir,
    Windows locks the running exe. A detached helper polls, deleting once the
    exiting installer releases the lock, so removal does not race a fixed delay.
    """

    install_dir = install_dir.resolve()

    # Use PowerShell with a hidden window; cmd.exe can flash a console window.
    # Poll: try the delete, stop as soon as the dir is gone, otherwise wait for
    # the parent installer to finish exiting and try again.
    escaped = str(install_dir).replace("'", "''")
    attempts = str(_DEFERRED_DELETE_ATTEMPTS)
    interval = str(_DEFERRED_DELETE_INTERVAL_MS)
    script = (
        "$d = '" + escaped + "'; "
        "for ($i = 0; $i -lt " + attempts + "; $i++) { "
        "if (-not (Test-Path -LiteralPath $d)) { break } "
        "Remove-Item -LiteralPath $d -Recurse -Force -ErrorAction SilentlyContinue; "
        "if (-not (Test-Path -LiteralPath $d)) { break } "
        "Start-Sleep -Milliseconds " + interval + " "
        "}"
    )
    ps = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-WindowStyle",
        "Hidden",
        "-Command",
        script,
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
