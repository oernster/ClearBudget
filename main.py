"""Application entry point - composition root and Qt event loop.

Handles the full login lifecycle:
1. Open central users store.
2. If no users exist → first-run CreateUserDialog.
3. Show LoginDialog.
4. On success, open that user's budget database and show MainWindow.
5. On MainWindow.switch_user_requested → hide the window, loop back to
   step 3; cancelling there returns to the window that is still open.
6. On MainWindow.sign_out_requested → destroy the window and close the
   database, loop back to step 3; cancelling there quits, because the
   session it would have returned to no longer exists.
"""

import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from clear_budget.auth.models import User
from clear_budget.auth.remembered_login import RememberedLogin
from clear_budget.auth.user_store import UserStore
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.session_database import (
    load_currency,
    open_user_database,
)
from clear_budget.shared import diagnostics
from clear_budget.shared.config import Config
from clear_budget.ui import _window_geometry as geom
from clear_budget.ui import startup
from clear_budget.ui.login_flow import run_login_flow
from clear_budget.ui.window_builder import build_main_window
from clear_budget.ui._window_geometry import default_window_rect
from clear_budget.ui.main_window import MainWindow
from clear_budget.ui.theme import apply_theme, load_saved_theme


def main() -> int:
    """Initialize application and start event loop."""
    started = startup.begin()
    if started is None:
        return 0
    # `started` is held for the whole function on purpose: it carries the
    # single-instance lock, which releases the moment nothing references it.
    app = started.app
    _avail = started.available
    icon_path = started.icon_path

    from clear_budget.ui import launch_screen
    from clear_budget.ui.raise_watcher import RaiseWatcher

    apply_theme(app, load_saved_theme())

    Config.app_dir().mkdir(parents=True, exist_ok=True)
    user_store = UserStore(Config.users_db_path())
    remembered_login = RememberedLogin(Config.app_dir())

    _active_database: list[Database] = []
    # The window this session is currently showing, held as a list because a
    # closure cannot rebind an enclosing name. It is what makes a cancelled
    # Switch User survivable: the old window is only HIDDEN by a switch, so
    # it can be shown again rather than the application being quit.
    _active_window: list["MainWindow"] = []

    def _window_to_raise():
        """The window a second launch should be shown, else None.

        The main window while there is one; otherwise whatever is on screen,
        which during sign-in is the sign-in dialog. Raising that is right: it
        is the window the user is being asked to deal with.
        """
        if _active_window:
            return _active_window[0]
        return QApplication.activeWindow()

    RaiseWatcher(app_dir=Config.app_dir(), window_provider=_window_to_raise, parent=app)

    def _drop_window() -> None:
        """Forget and destroy the tracked window, leaving no live window.

        Used where the session is deliberately torn down rather than replaced
        (a full restore): the account that signs in next may not be the one
        that signed in before; it may not exist at all.
        """
        while _active_window:
            _active_window.pop().deleteLater()

    def _show_window(user: "User", window: "MainWindow") -> None:
        """Apply icon, geometry and signals, then show the window.

        Replacing the tracked window is part of showing one: the window it
        supersedes is destroyed here, so no hidden MainWindow is left holding
        a stale database connection and a stale view of the budget.
        """
        _drop_window()
        _active_window.append(window)
        if icon_path:
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                window.setWindowIcon(icon)
        # Geometry first so the window is created on the launch monitor at the
        # right size, then show, then centre: the frame margins and any size
        # the layout insists on are only knowable once the window exists.
        window.setGeometry(
            *default_window_rect(
                available=_avail,
                width_fraction=geom.WINDOW_WIDTH_FRACTION,
                height_fraction=geom.WINDOW_HEIGHT_FRACTION,
                min_width=geom.MIN_WINDOW_WIDTH_PT,
                min_height=geom.MIN_WINDOW_HEIGHT_PT,
            )
        )
        window.show()
        launch_screen.centre(window)
        window.switch_user_requested.connect(_session_loop)
        window.sign_out_requested.connect(_sign_out)
        window.database_replaced.connect(lambda: _reload_database(user, window))
        window.full_restore_requested.connect(
            lambda path: _restore_everything(path, window)
        )
        window.database_load_requested.connect(
            lambda path: _load_database(path, user, window)
        )

    def _sign_out() -> None:
        """End the session, then offer the sign-in screen with none running.

        The difference from a switch is the whole point of having both. A
        switch leaves the window and its database alive, so a cancelled
        sign-in returns to them. Signing out destroys the window and closes
        the database here, so there is nothing to return to and the same
        cancel closes the application, exactly as it does at first launch.
        Nothing is lost either way: the budget is on disk.
        """
        _drop_window()
        if _active_database:
            _active_database[0].close()
            _active_database.clear()
        diagnostics.log("signed out; session ended")
        _session_loop()

    def _load_database(source: str, user: "User", old_window: "MainWindow") -> None:
        """Put a chosen database in place as this session's active budget.

        The ordering is the whole point and it belongs here because only the
        composition root owns the connection. CLOSE first, then replace, then
        reopen. Doing it the other way round (replacing the file while the
        connection was still open) is what destroyed two real budgets: the
        swap succeeds silently on Windows, the live connection keeps writing
        against the database it thinks is there and what is left afterwards
        is the right length and entirely zero bytes.

        A failure to replace leaves the existing database untouched, so the
        session simply carries on with the budget it already had.
        """
        from clear_budget.shared.db_copy import (
            DatabaseCopyError,
            replace_closed_database,
        )

        old_window.hide()
        target = old_window.db_path
        if _active_database:
            _active_database[0].close()
            _active_database.clear()
        try:
            replace_closed_database(Path(source), Path(target))
        except DatabaseCopyError as exc:
            QMessageBox.critical(
                None,
                "Load Failed",
                f"The database could not be loaded, so nothing was "
                f"changed:\n\n{exc}",
            )
        _reload_database(user, old_window)

    def _reload_database(user: "User", old_window: "MainWindow") -> None:
        """Reload the database in-place after an import or settings change."""
        old_window.hide()
        if _active_database:
            _active_database[0].close()
            _active_database.clear()
        database = open_user_database(user.username)
        _active_database.append(database)
        load_currency(database)
        diagnostics.log("reloaded budget %s", database.db_path)
        window = build_main_window(database, user, user_store)
        _show_window(user, window)
        diagnostics.log("main window rebuilt")

    def _restore_everything(zip_path: str, old_window: "MainWindow") -> None:
        """Swap in a full backup, then return to the sign-in screen.

        Only this composition root can do it: the open budget database and
        the accounts store must CLOSE before the files can be replaced (an
        open database cannot be swapped on Windows) and the user signing in
        afterwards may not even exist any more, so the session is torn down
        rather than reloaded. The zip was validated and double-confirmed by
        the UI flow before the signal fired; the restore validates again in
        staging before touching a live file, so a failure leaves everything
        as it was and simply returns to sign-in.
        """
        nonlocal user_store
        from clear_budget.auth.full_backup import FullBackupError, restore_full_backup

        old_window.hide()
        if _active_database:
            _active_database[0].close()
            _active_database.clear()
        user_store.close()
        try:
            restore_full_backup(package_path=Path(zip_path), app_dir=Config.app_dir())
        except (FullBackupError, OSError) as exc:
            QMessageBox.warning(None, "Restore Everything", str(exc))
        user_store = UserStore(Config.users_db_path())
        _drop_window()
        _session_loop()

    def _session_loop() -> None:
        """Run login → main window → (optional) re-login cycle."""
        signed_in = run_login_flow(user_store, remembered_login)
        if signed_in is None:
            if _active_window:
                # Switch User was cancelled. The window that asked for the
                # switch is merely hidden and its database is still open, so
                # the session it belongs to resumes exactly where it was.
                # Quitting here instead closed the whole application, which
                # is what a cancel must never do.
                diagnostics.log("login flow cancelled; resuming open session")
                window = _active_window[0]
                window.show()
                window.raise_()
                window.activateWindow()
                return
            diagnostics.log("login flow returned no user; quitting")
            app.quit()
            return

        user = signed_in.user
        # The sign-in screen stays up from here until there is a window to
        # hand over to. Building one takes seconds on a slower machine and
        # the screen was empty for every one of them.
        try:
            signed_in.screen.begin_handover()
            if _active_database:
                _active_database[0].close()
                _active_database.clear()

            diagnostics.log("signed in as %s", user.username)
            try:
                database = open_user_database(user.username)
            except sqlite3.DatabaseError as exc:
                diagnostics.log("FAILED opening budget for %s: %s", user.username, exc)
                # Without this the sign-in simply produced NOTHING: the error
                # escaped the timer slot, a windowed build has nowhere to print
                # it and no window was ever shown. An unreadable budget is the
                # one failure the user must be told about, since it is the one
                # a backup exists to answer.
                QMessageBox.critical(
                    None,
                    "Budget Could Not Be Opened",
                    "This account's budget database could not be opened:\n\n"
                    f"{exc}\n\n"
                    "The file may be damaged. Restore it from a backup or use "
                    "File > Import / Export > Restore Everything after signing "
                    "in as an administrator.",
                )
                signed_in.screen.end_handover()
                _session_loop()
                return
            _active_database.append(database)
            load_currency(database)

            diagnostics.log("opened budget %s", database.db_path)
            window = build_main_window(
                database, user, user_store, progress=signed_in.screen.report_progress
            )
            _show_window(user, window)
            # Only now: the window it hands over to exists and is on screen.
            signed_in.screen.end_handover()
            diagnostics.log("main window shown")
        finally:
            # The backstop, not the ordinary route: both paths above close
            # the screen themselves, at the exact moment they have something
            # to hand over to. This catches the third case, an exception,
            # which would otherwise strand the screen on top of nothing,
            # inert and unclosable, the guard that makes it inert being
            # lifted only here. `end_handover` is idempotent for this.
            signed_in.screen.end_handover()

    QTimer.singleShot(0, _session_loop)

    result = app.exec()
    diagnostics.log("event loop returned %s, shutting down", result)
    if _active_database:
        _active_database[0].close()
    user_store.close()
    return result


if __name__ == "__main__":
    sys.exit(main())
