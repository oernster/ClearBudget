"""The monitor the app opens on.

Qt puts a parentless top-level window on the PRIMARY screen, so on a
multi-monitor desktop every ClearBudget window arrived on the primary display
however the user actually started the app. From four monitors that reads as
the app picking one at random.

Nothing in the shell tells a process which monitor its launch click happened
on, so there is no exact answer to ask for. The pointer's screen at startup
is the closest proxy available; it is also the one desktop apps generally use:
a double-clicked shortcut, a Start-menu or taskbar click and the installer's
Launch button all happen under the pointer. A launch with no pointer involved
(a keyboard-driven Start-menu search, a scheduled task) falls back to the
primary screen, which is no worse than the behaviour it replaces.

The screen is resolved ONCE, during startup; every window in the session
uses that one. Re-reading the pointer per window would bring the same
arbitrariness back from the other end, opening a dialog on whichever monitor
the mouse happened to be resting on at the time.

Mirrors ui_scale: the composition root calls init() once, everything else
reads.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor, QGuiApplication

from clear_budget.ui._window_geometry import Rect, centred_position

_screen = None


def init() -> None:
    """Resolve the launch screen. Call once, after the QApplication exists."""
    global _screen
    _screen = QGuiApplication.screenAt(QCursor.pos())


def screen():
    """The launch screen, falling back to the primary one."""
    return _screen or QGuiApplication.primaryScreen()


def available() -> Rect:
    """The launch screen's usable area as (x, y, width, height)."""
    target = screen()
    if target is None:
        return (0, 0, 0, 0)
    rect = target.availableGeometry()
    return (rect.x(), rect.y(), rect.width(), rect.height())


def centre(window) -> None:
    """Centre `window`'s visible frame on the launch screen, without resizing.

    Placed TWICE on purpose. Once now, so the window is created on the right
    monitor at roughly the right spot and never jumps across displays. Then
    again as soon as the event loop turns, because two things are unknown
    until the window actually exists: the frame margins Qt adds around the
    client area, plus whether the layout forced the window wider or taller
    than the size it was given. Either leaves a once-placed window off
    centre, the second badly so. The correction happens before the first
    paint, so it is not visible.
    """
    _place(window)
    QTimer.singleShot(0, window, lambda: _place(window))


def _place(window) -> None:
    """Move `window` so its frame is centred on the launch screen."""
    if screen() is None:
        return
    # frameGeometry() is the client rect until the window is created, so fall
    # back to the size hint for a window that has not been shown yet.
    frame, hint = window.frameGeometry(), window.sizeHint()
    window.move(
        *centred_position(
            available=available(),
            size=(
                max(frame.width(), hint.width()),
                max(frame.height(), hint.height()),
            ),
        )
    )
