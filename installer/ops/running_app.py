"""Detecting, closing and launching the installed application.

An install replaces every file in the bundle, so it must not run while the
application holds its own executable open. The setup program therefore detects
a running instance and offers to end it, rather than only telling the user to
go and do it themselves.

Ending it is a forced termination rather than a polite close request. Asking a
window to close leaves it to the application whether to honour that; a
process that declines still holds the file lock, so the guarantee the caller
needs (the lock is gone) would not hold. The offer states plainly that the
running session ends.

Processes are matched on the resolved executable path rather than on the image
name, so an unrelated copy of the application living somewhere else is neither
counted nor ended.

Every process query and every kill goes through an injectable
``ProcessController``, so the whole flow is exercised in tests without a real
process ever being listed or ended. British spelling is used in comments.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

import psutil

from installer.ops.commands import CommandRunner, default_runner
from installer.ops.errors import AppStillRunningError

# How long to wait for the processes to disappear once they have been ended, so
# a stuck process cannot hang the setup program indefinitely.
CLOSE_POLL_ATTEMPTS = 50
CLOSE_POLL_INTERVAL_S = 0.1

CLOSE_FAILED_MESSAGE = (
    "ClearBudget could not be closed. Please close it by hand, then try again."
)

_EXE_ATTR = "exe"
_PID_ATTR = "pid"

# Injected so the wait can be exercised without spending real time.
Sleeper = Callable[[float], None]


class ProcessController(Protocol):
    """Lists and ends the processes running a given executable."""

    def running_pids(self, exe_path: Path) -> tuple[int, ...]:
        """Return the process ids currently running ``exe_path``."""
        ...

    def kill(self, pid: int) -> None:
        """End one process by id, forcefully and without asking it to agree."""
        ...


def default_process_iter() -> Iterable[object]:
    """Return the live process list, carrying the two attributes we read."""
    return psutil.process_iter(attrs=[_PID_ATTR, _EXE_ATTR])


def _default_kill(pid: int) -> None:  # pragma: no cover
    """End a real process. Never exercised: a test must not kill anything."""
    psutil.Process(pid).kill()


def _pid_if_running(proc: object, wanted: Path) -> int | None:
    """Return the process id when this process runs ``wanted``, else None."""
    try:
        raw = getattr(proc, "info", {}).get(_EXE_ATTR)
        if not raw:
            return None
        if Path(raw).resolve() != wanted:
            return None
        return int(getattr(proc, "info", {})[_PID_ATTR])
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError, ValueError, TypeError):
        # Best effort: a process that cannot be inspected is treated as not
        # ours, so a permissions failure never blocks a legitimate install.
        return None


class PsutilProcessController:
    """The real controller, reading and ending processes through psutil.

    The two calls that touch live processes are injected rather than made
    directly, so the matching and the error handling around them are tested
    against hand-written processes instead of real ones.
    """

    def __init__(
        self,
        iter_processes: Callable[[], Iterable[object]] | None = None,
        kill_process: Callable[[int], None] | None = None,
    ) -> None:
        self._iter_processes = iter_processes or default_process_iter
        self._kill_process = kill_process or _default_kill

    def running_pids(self, exe_path: Path) -> tuple[int, ...]:
        """Return the ids of every process whose executable resolves to this one."""
        wanted = exe_path.resolve()
        found = [
            pid
            for pid in (
                _pid_if_running(proc, wanted) for proc in self._iter_processes()
            )
            if pid is not None
        ]
        return tuple(found)

    def kill(self, pid: int) -> None:
        """End a process, ignoring one that has already gone or is protected."""
        try:
            self._kill_process(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            return


def default_controller() -> ProcessController:
    """Return the controller used when a caller does not supply one."""
    return PsutilProcessController()


def is_app_running(
    exe_path: Path,
    controller: ProcessController | None = None,
) -> bool:
    """Return True when at least one process is running ``exe_path``."""
    active = controller or default_controller()
    return bool(active.running_pids(exe_path))


def close_running_app(
    exe_path: Path,
    controller: ProcessController | None = None,
    *,
    sleep: Sleeper | None = None,
) -> None:
    """End every process running ``exe_path`` and wait for the lock to release.

    Ending the process is not the same as the file lock going: Windows releases
    the handle a moment afterwards. The wait is bounded; an application
    still present at the end raises AppStillRunningError, so the caller never
    proceeds onto a locked file believing it is free.
    """
    active = controller or default_controller()
    wait = sleep or time.sleep

    for pid in active.running_pids(exe_path):
        active.kill(pid)

    for _ in range(CLOSE_POLL_ATTEMPTS):
        if not is_app_running(exe_path, active):
            return
        wait(CLOSE_POLL_INTERVAL_S)

    if is_app_running(exe_path, active):
        raise AppStillRunningError(CLOSE_FAILED_MESSAGE)


def launch_app(exe_path: Path, runner: CommandRunner | None = None) -> None:
    """Start the freshly installed application, detached from the installer.

    Detached on purpose: the setup program is about to be closed by the user
    and the application must not go with it. The working directory is the
    install root, which is where the application expects to find its bundle.
    """
    active = runner or default_runner()
    active.start_detached([str(exe_path)], cwd=str(exe_path.parent))
