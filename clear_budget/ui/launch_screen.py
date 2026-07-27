"""The monitor the app opens on.

Qt puts a parentless top-level window on the PRIMARY screen, so on a
multi-monitor desktop every ClearBudget window arrived on the primary display
however the user actually started the app. From four monitors that reads as
the app picking one at random.

Nothing in the shell tells a process which monitor its launch click happened
on, so there is no exact answer to ask for. The pointer's screen at startup
is the closest proxy available, and it is the one desktop apps generally use:
a double-clicked shortcut, a Start-menu or taskbar click and the installer's
Launch button all happen under the pointer. A launch with no pointer involved
(a keyboard-driven Start-menu search, a scheduled task) falls back to the
primary screen, which is no worse than the behaviour it replaces.

The screen is resolved ONCE, during startup, and every window in the session
uses that one. Re-reading the pointer per window would bring the same
arbitrariness back from the other end, opening a dialog on whichever monitor
the mouse happened to be resting on at the time.

Mirrors ui_scale: the composition root calls init() once, everything else
reads.
"""

from __future__ import annotations

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
    """Move `window` to the middle of the launch screen, without resizing it.

    Sized from the larger of the window's current size and its size hint, so
    a dialog that has already been given a size keeps it and one that has not
    is placed for the size it is about to take rather than for Qt's unshown
    default.
    """
    if screen() is None:
        return
    size, hint = window.size(), window.sizeHint()
    window.move(
        *centred_position(
            available=available(),
            size=(max(size.width(), hint.width()), max(size.height(), hint.height())),
        )
    )
