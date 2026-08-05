"""Removing the install directory.

Two paths, chosen by where the running uninstaller lives. Run from outside the
install directory, nothing locks it (the application is already confirmed not
running), so the delete is synchronous and any failure is surfaced. The copy of
the setup program that "Apps & features" invokes lives inside the directory it
has to remove and cannot delete its own running executable, so that one hands
the deletion to a detached helper which polls until the lock is released rather
than racing a fixed delay.

The helper is launched through the injectable CommandRunner, so a test observes
the command instead of spawning it. British spelling is used in comments.
"""

from __future__ import annotations

import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path

from installer.ops.commands import CommandRunner, default_runner, powershell_command
from installer.ops.errors import InstallerOperationError

# Direct (synchronous) delete: a brief bounded retry rides out transient locks
# (an anti-virus scanner holding a handle, say) before the failure is surfaced.
DIRECT_DELETE_ATTEMPTS = 5
DIRECT_DELETE_INTERVAL_S = 0.5

# Deferred delete: the detached helper polls rather than sleeping once, so the
# directory goes as soon as the exiting installer releases its lock.
DEFERRED_DELETE_ATTEMPTS = 30
DEFERRED_DELETE_INTERVAL_MS = 500

_QUOTE = "'"
_ESCAPED_QUOTE = "''"

# Injected so the retry can be exercised without spending real time.
Sleeper = Callable[[float], None]


def running_from_inside(install_dir: Path) -> bool:
    """Return True when this process's executable lives inside ``install_dir``.

    A path that cannot be resolved answers True, which is the safe direction:
    the caller then defers the deletion instead of attempting it in place.
    """
    try:
        running = Path(sys.executable).resolve()
        install_dir = install_dir.resolve()
    except OSError:  # pragma: no cover
        # Defensive: resolve() does not raise for any path this environment can
        # produce, so no test can reach this. It is kept because answering True
        # defers the deletion, which is the safe direction.
        return True
    return running == install_dir or install_dir in running.parents


def deferred_delete_script(install_dir: Path) -> str:
    """Return the script that removes the directory once the lock is released."""
    escaped = str(install_dir).replace(_QUOTE, _ESCAPED_QUOTE)
    return (
        f"$d = '{escaped}'; "
        f"for ($i = 0; $i -lt {DEFERRED_DELETE_ATTEMPTS}; $i++) {{ "
        "if (-not (Test-Path -LiteralPath $d)) { break } "
        "Remove-Item -LiteralPath $d -Recurse -Force "
        "-ErrorAction SilentlyContinue; "
        "if (-not (Test-Path -LiteralPath $d)) { break } "
        f"Start-Sleep -Milliseconds {DEFERRED_DELETE_INTERVAL_MS} "
        "}"
    )


def schedule_delete_after_exit(
    install_dir: Path,
    runner: CommandRunner | None = None,
) -> None:
    """Delete the install directory from a detached helper once this exits."""
    active = runner or default_runner()
    script = deferred_delete_script(install_dir.resolve())
    active.start_detached(powershell_command(script, hidden=True))


def delete_install_dir_now(
    install_dir: Path,
    *,
    sleep: Sleeper | None = None,
) -> None:
    """Delete ``install_dir`` synchronously, retrying briefly on transient locks.

    Used when the installer runs from outside the directory, so removal is
    fully under our control and a failure is raised rather than swallowed.
    """
    install_dir = install_dir.resolve()
    wait = sleep or time.sleep
    last_error: OSError | None = None

    for attempt in range(DIRECT_DELETE_ATTEMPTS):
        try:
            shutil.rmtree(install_dir)
        except FileNotFoundError:
            return
        except OSError as exc:
            last_error = exc
        if not install_dir.exists():
            return
        if attempt < DIRECT_DELETE_ATTEMPTS - 1:
            wait(DIRECT_DELETE_INTERVAL_S)

    raise InstallerOperationError(
        f"Could not remove the install directory at {install_dir}: {last_error}"
    )


def remove_install_dir(
    install_dir: Path,
    runner: CommandRunner | None = None,
    *,
    sleep: Sleeper | None = None,
) -> None:
    """Remove the install directory, deferring when it holds the running exe."""
    if running_from_inside(install_dir):
        schedule_delete_after_exit(install_dir, runner)
        return
    delete_install_dir_now(install_dir, sleep=sleep)
