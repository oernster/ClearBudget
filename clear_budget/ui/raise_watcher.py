"""Watches for a second launch asking to be shown; shows the window when one is.

The other half of `shared.raise_request`. A launch that finds the lock held
leaves a request and exits; this is what picks it up, so clicking the icon
again brings the application forward instead of appearing to do nothing.

A poll rather than a file-system notification: the request is a single empty
file written at most once per launch, so the cost is one `unlink` attempt a
second; a poll also behaves identically on a network share where change
notifications do not arrive.

The window is fetched through a callable rather than held, because it is
replaced whenever a budget is reloaded or an account switches. Holding one
here would raise a window that had already been destroyed.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer

from clear_budget.shared.foreground import force_foreground
from clear_budget.shared.raise_request import consume_raise_request

# Fast enough that a second click feels answered, slow enough to be free.
POLL_INTERVAL_MS = 750


def bring_to_front(window) -> None:
    """Restore, raise and focus `window`, whatever state it was left in.

    All three steps are needed and none replaces another: a minimised window
    ignores `raise_`; a raised window does not necessarily take focus;
    `activateWindow` on its own leaves a minimised window minimised. On
    Windows even all three are not enough, which was measured, not assumed:
    see `shared.foreground`.
    """
    state = window.windowState()
    window.setWindowState(
        (state & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive
    )
    window.show()
    window.raise_()
    window.activateWindow()
    force_foreground(int(window.winId()))


class RaiseWatcher(QObject):
    """Polls for a raise request and answers it by showing the window."""

    def __init__(self, *, app_dir, window_provider: Callable[[], object], parent=None):
        super().__init__(parent)
        self._app_dir = app_dir
        self._window_provider = window_provider
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(POLL_INTERVAL_MS)

    def _tick(self) -> None:
        if not consume_raise_request(app_dir=self._app_dir):
            return
        window = self._window_provider()
        if window is None:
            return
        bring_to_front(window)
