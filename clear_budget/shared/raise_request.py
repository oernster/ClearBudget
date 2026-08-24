"""How a second launch asks the copy already running to come to the front.

The single-instance lock (see `single_instance`) stops two writers reaching one
SQLite file. On its own it makes the second launch look like nothing happened:
the process exits and the window the user actually wanted stays wherever it
was, possibly behind everything else. Clicking the icon again is a request to
SEE the application, so the second launch leaves a request the running copy
picks up, then exits without a word.

A file in the data directory is the whole channel. It needs no socket, no port
and no extra Qt module; it also works the same on all three platforms, which
matters because the alternative (finding the other process's window) is a
different piece of Win32 on every one of them.

Windows will not let a background process take the foreground on its own, so
the ask is a two-part move: the STARTING process calls AllowSetForegroundWindow
first, which is the running copy's permission to come forward; only then does
it write the request. Without that call the other window flashes in the task bar
rather than rising.

Every platform detail arrives through a parameter with a real default, so both
branches are exercised anywhere with hand-written fakes.

British spelling is used in comments.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REQUEST_FILENAME = "raise_request"

# AllowSetForegroundWindow's "any process may take the foreground" argument.
# The running copy's process id is not known here; nor does it need to be:
# the permission lasts only until the next foreground change.
ASFW_ANY = -1

_WINDOWS = "win32"


def _default_user32() -> Any:  # pragma: no cover - Windows API handle
    import ctypes

    return ctypes.windll.user32


def request_raise(
    *,
    app_dir: Path,
    platform: str | None = None,
    user32: Any | None = None,
) -> bool:
    """Ask the running copy to show itself. True when the ask was left.

    False means the data directory could not be written, which is not worth
    stopping for: the launch is exiting either way and the only thing lost is
    the other window coming forward.
    """
    if (sys.platform if platform is None else platform) == _WINDOWS:
        (user32 or _default_user32()).AllowSetForegroundWindow(ASFW_ANY)
    try:
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / REQUEST_FILENAME).write_text("", encoding="utf-8")
    except OSError:
        return False
    return True


def consume_raise_request(*, app_dir: Path) -> bool:
    """True when a launch asked to be shown; the ask is spent either way.

    Spending it is the deletion itself, so two launches in quick succession
    raise the window once rather than queueing; a request left behind by a
    crash is cleared the first time it is read.
    """
    try:
        (app_dir / REQUEST_FILENAME).unlink()
    except OSError:
        return False
    return True
