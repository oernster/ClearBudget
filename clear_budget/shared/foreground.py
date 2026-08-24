"""Taking the foreground on Windows, which a background process cannot just do.

Windows refuses `SetForegroundWindow` from a process that does not already own
the foreground, so that a background program cannot steal what the user is
typing into. The application asking to come forward is exactly the case the
rule is not meant to catch: the user just clicked its icon.

`AllowSetForegroundWindow`, which the starting copy calls (see `raise_request`),
is not enough on its own: the granting process must itself be the foreground
process at the time; a launcher that has not drawn a window never is. This
was measured rather than assumed. With only that call, a second launch left the
first copy exactly where it was.

What does work is briefly joining the input queue of whichever thread owns the
foreground. While two threads share an input queue, Windows treats them as one
for the purposes of that rule, so the call is allowed; the attachment is undone
immediately afterwards, so nothing is left sharing state.

Every API arrives through a parameter with a real default, so the whole
sequence is exercised anywhere with hand-written fakes.

British spelling is used in comments.
"""

from __future__ import annotations

import sys
from typing import Any

_WINDOWS = "win32"


def _default_user32() -> Any:  # pragma: no cover - Windows API handle
    import ctypes

    return ctypes.windll.user32


def _default_kernel32() -> Any:  # pragma: no cover - Windows API handle
    import ctypes

    return ctypes.windll.kernel32


def force_foreground(
    window_handle: int,
    *,
    platform: str | None = None,
    user32: Any | None = None,
    kernel32: Any | None = None,
) -> bool:
    """Bring `window_handle` to the foreground. True when the call was made.

    False on any platform but Windows, where the toolkit's own raise is
    sufficient and there is nothing to work around.
    """
    if (sys.platform if platform is None else platform) != _WINDOWS:
        return False

    api = user32 or _default_user32()
    kernel = kernel32 or _default_kernel32()

    foreground = api.GetForegroundWindow()
    holder_thread = api.GetWindowThreadProcessId(foreground, None)
    own_thread = kernel.GetCurrentThreadId()

    # Already ours, else the same thread: attaching a thread to itself fails.
    attached = holder_thread != own_thread and bool(
        api.AttachThreadInput(own_thread, holder_thread, True)
    )
    try:
        api.BringWindowToTop(window_handle)
        api.SetForegroundWindow(window_handle)
    finally:
        if attached:
            api.AttachThreadInput(own_thread, holder_thread, False)
    return True
