"""One running copy of the application per user, per platform.

Two budgets open on one database is not a UI annoyance, it is two writers
against the same SQLite file, so the lock is a data-integrity guard rather
than a convenience.

Windows takes a named kernel mutex; macOS and Linux take an exclusive
advisory lock on a file in the data directory, because `ctypes.windll`
exists only on Windows. Both return an opaque handle the caller must keep
alive for the process's lifetime: the lock is released when the handle is
dropped or the process exits, so storing it in a local that goes out of
scope silently unlocks.

Every platform detail arrives through a parameter with a real default, so
both branches are exercised on any machine with hand-written fakes and
neither needs the operating system it describes.

British spelling is used in comments.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

MUTEX_NAME = "Global\\ClearBudget_SingleInstance"
LOCK_FILENAME = "clearbudget.lock"

# GetLastError's code from CreateMutexW when the named mutex already exists,
# which is precisely "another instance holds it".
WIN_ERROR_ALREADY_EXISTS = 183

_WINDOWS = "win32"


def _default_kernel32() -> Any:  # pragma: no cover - Windows API handle
    import ctypes

    return ctypes.windll.kernel32


def _default_flock() -> Callable[..., None]:  # pragma: no cover - POSIX only
    import fcntl

    def lock(handle: int) -> None:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    return lock


def acquire(
    *,
    app_dir: Path,
    platform: str | None = None,
    kernel32: Any | None = None,
    flock: Callable[[int], None] | None = None,
) -> Any | None:
    """Take the single-instance lock; return a handle, else None when held.

    The returned handle is opaque and must be kept alive for as long as the
    application runs.
    """
    platform = sys.platform if platform is None else platform
    if platform == _WINDOWS:
        return _acquire_windows(kernel32 or _default_kernel32())
    return _acquire_posix(app_dir, flock or _default_flock())


def _acquire_windows(kernel32: Any) -> Any | None:
    """A named kernel mutex, released when the process exits."""
    handle = kernel32.CreateMutexW(None, True, MUTEX_NAME)
    if kernel32.GetLastError() == WIN_ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return handle


def _acquire_posix(app_dir: Path, flock: Callable[[int], None]) -> Any | None:
    """An exclusive advisory lock on a file in the data directory."""
    app_dir.mkdir(parents=True, exist_ok=True)
    # Deliberately not a context manager: closing the file releases the lock,
    # so the handle has to outlive this function.
    lock_file = open(app_dir / LOCK_FILENAME, "w")  # noqa: SIM115 (held until exit)
    try:
        flock(lock_file.fileno())
    except OSError:
        lock_file.close()
        return None
    return lock_file
