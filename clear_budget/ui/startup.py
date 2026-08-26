"""Bringing the process up; else handing over to the copy already running.

Everything that has to happen before a single window can be built, in the one
order that works: move the data directory before anything reads it, install
the log before anything can fail, take the single-instance lock before two
writers can reach one budget, then resolve the monitor the app was launched
from before anything is shown.

Split out of `main.py`, which was at 388 lines and so inside the band the size
cap treats as one edit from failing (tests/structural/test_loc_limits.py). It
is a cohesive slice rather than an arbitrary one: the composition root is left
owning the session, the windows and the database connection, which is what
only it can do.

The second launch is answered here too. Finding the lock held is no longer a
refusal: the copy already running is asked to come forward and this process
leaves without a word, because clicking the icon a second time is a request to
SEE the application, not to run two of them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from clear_budget.shared import diagnostics, raise_request, single_instance
from clear_budget.shared.config import APP_DIR_ENV_VAR, Config
from clear_budget.shared.data_migration import migrate_legacy_data
from clear_budget.shared.resources import find_runtime_window_icon
from clear_budget.ui import _window_geometry as geom
from clear_budget.version import __version__


@dataclass(frozen=True, slots=True)
class Startup:
    """What the composition root needs from a successful start.

    Attributes:
        app: The QApplication, whose event loop main runs.
        available: The launch monitor's available geometry, so every window
            this session opens lands on the display the app was started from.
        icon_path: The window icon; None when it cannot be resolved.
        lock: The single-instance handle. Held for the process's lifetime:
            dropping it releases the lock and lets a second copy start.
    """

    app: QApplication
    available: dict
    icon_path: object
    lock: object


def begin() -> Startup | None:
    """Start the process; None when another copy was asked to come forward."""
    # The one-time data-directory move runs FIRST: before the single-instance
    # lock (which lives in the data directory on macOS and Linux) and before
    # anything reads a setting. A redirected run (CLEARBUDGET_HOME set: the
    # suite, a probe) never migrates real data. If the move cannot complete,
    # resolution keeps preferring the still-present legacy directory, so the
    # app runs on the data it always had and retries at the next launch.
    if not os.environ.get(APP_DIR_ENV_VAR, "").strip():
        migrate_legacy_data(
            legacy=Config.legacy_app_dir(), target=Config.platform_app_dir()
        )

    app = QApplication([])

    # Before any widget exists, so nothing is built against the bare style:
    # tooltips on the icon buttons appear promptly rather than after Qt's
    # 700ms default (clear_budget/ui/tooltip_style.py has the numbers).
    from clear_budget.ui import tooltip_style

    tooltip_style.install(app)

    diagnostics.install(Config.app_dir() / "logs")
    diagnostics.log(
        "session starting, version %s, data dir %s", __version__, Config.app_dir()
    )

    lock = single_instance.acquire(app_dir=Config.app_dir())
    if lock is None:
        raise_request.request_raise(app_dir=Config.app_dir())
        diagnostics.log("already running; asked the open copy to come forward")
        return None

    # Clear anything a previous run left behind, so the watcher's first tick
    # does not answer a request nobody made.
    raise_request.consume_raise_request(app_dir=Config.app_dir())

    from clear_budget.ui import launch_screen, ui_scale

    # Resolve the monitor the app was started from before anything is shown,
    # so every window this session opens lands there rather than on whichever
    # display happens to be primary.
    launch_screen.init()
    available = launch_screen.available()
    ui_scale.init(
        min(
            available[geom.AVAILABLE_HEIGHT] / geom.UI_SCALE_REFERENCE_HEIGHT_PT,
            geom.MAX_UI_SCALE_FACTOR,
        )
    )

    icon_path = find_runtime_window_icon()
    if icon_path:
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            app.setWindowIcon(icon)

    return Startup(app=app, available=available, icon_path=icon_path, lock=lock)
