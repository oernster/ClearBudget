"""Application entry point - composition root and Qt event loop.

Handles the full login lifecycle:
1. Open central users store.
2. If no users exist → first-run CreateUserDialog.
3. Show LoginDialog.
4. On success, open that user's budget database and show MainWindow.
5. On MainWindow.logout_requested → close window, loop back to step 3.
"""

import sqlite3
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.application.services.update_service import (
    UpdateService,
    platform_key_for,
)
from clear_budget.auth.models import User
from clear_budget.auth.remembered_login import RememberedLogin
from clear_budget.auth.user_store import UserStore
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)
from clear_budget.infrastructure.update.github_release_source import (
    GitHubReleaseSource,
)
import os

from clear_budget.shared.config import APP_DIR_ENV_VAR, Config
from clear_budget.shared.currency import set_currency
from clear_budget.shared.data_migration import migrate_legacy_data
from clear_budget.shared.resources import find_runtime_window_icon
from clear_budget.shared import single_instance
from clear_budget.ui import _window_geometry as geom
from clear_budget.ui._window_geometry import default_window_rect
from clear_budget.version import __version__
from clear_budget.ui.main_window import MainWindow
from clear_budget.ui.theme import apply_theme, load_saved_theme
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel


def _run_login_flow(
    user_store: UserStore, remembered_login: RememberedLogin
) -> User | None:
    """Show first-run or login dialog.  Returns authenticated User or None (quit)."""
    from clear_budget.ui import launch_screen
    from clear_budget.ui.widgets.create_user_dialog import CreateUserDialog
    from clear_budget.ui.widgets.login_dialog import LoginDialog

    if not user_store.has_users():
        dlg = CreateUserDialog(user_store, is_first_user=True)
        # These have no parent to be centred on, so without this they take
        # Qt's default placement on the primary screen.
        launch_screen.centre(dlg)
        if dlg.exec() != CreateUserDialog.Accepted or dlg.created_user is None:
            return None
        # First user just created - log them in directly.
        return dlg.created_user

    dlg = LoginDialog(user_store, remembered_login)
    launch_screen.centre(dlg)
    if dlg.exec() != LoginDialog.Accepted:
        return None
    return dlg.authenticated_user


def _open_user_database(username: str) -> Database:
    """Open (or create) the ACTIVE budget database for username.

    Which budget that is comes from the user's registry, which synthesises the
    legacy single budget when it has never been written. Switching budget is
    therefore a registry write plus the existing `database_replaced` reload,
    with no new session plumbing: this one function is the only place that
    decides which file a session opens.
    """
    from clear_budget.shared.budget_registry import active_db_path

    config = Config.for_user(username)
    config.ensure_directories()
    database = Database(active_db_path(username))
    database.connect()
    database.create_schema()
    return database


def _load_currency(database: Database) -> None:
    """Activate the currency saved in this user's settings (defaults to GBP)."""
    if database.conn is None:
        return
    row = database.conn.execute(
        "SELECT value FROM settings WHERE key = 'currency'"
    ).fetchone()
    set_currency(row["value"] if row else "GBP")


def _build_main_window(
    database: Database,
    current_user: User,
    user_store: UserStore,
) -> MainWindow:
    """Wire all services and return a ready MainWindow."""
    bill_repo = SQLiteBillRepository(database.conn)
    income_repo = SQLiteIncomeSourceRepository(database.conn)
    payment_method_repo = SQLitePaymentMethodRepository(database.conn)
    month_generator = MonthGenerator(bill_repo, income_repo)
    budget_service = BudgetService(
        bill_repo=bill_repo,
        income_repo=income_repo,
        payment_method_repo=payment_method_repo,
        month_generator=month_generator,
    )
    budget_service.update_card_balances_for_elapsed_dates()
    budget_service.apply_elapsed_limit_changes()
    budget_service.apply_elapsed_bank_transactions()
    budget_service.auto_archive_elapsed_months(current_month=YearMonth.today())
    month_view_model = MonthViewModel(budget_service=budget_service)
    solvency_view_model = SolvencyViewModel(budget_service=budget_service)
    update_service = UpdateService(
        source=GitHubReleaseSource(),
        current_version=__version__,
        platform_key=platform_key_for(sys.platform),
    )
    return MainWindow(
        month_view_model=month_view_model,
        solvency_view_model=solvency_view_model,
        current_user=current_user,
        user_store=user_store,
        db_path=database.db_path,
        update_service=update_service,
    )


def main() -> int:
    """Initialize application and start event loop."""
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

    _instance_lock = single_instance.acquire(app_dir=Config.app_dir())
    if _instance_lock is None:
        QMessageBox.warning(None, "ClearBudget", "ClearBudget is already running.")
        return 1

    from clear_budget.ui import launch_screen, ui_scale

    # Resolve the monitor the app was started from before anything is shown,
    # so every window this session opens lands there rather than on whichever
    # display happens to be primary.
    launch_screen.init()
    _avail = launch_screen.available()
    _avail_h = _avail[geom.AVAILABLE_HEIGHT]
    ui_scale.init(
        min(_avail_h / geom.UI_SCALE_REFERENCE_HEIGHT_PT, geom.MAX_UI_SCALE_FACTOR)
    )

    icon_path = find_runtime_window_icon()
    if icon_path:
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            app.setWindowIcon(icon)

    apply_theme(app, load_saved_theme())

    Config.app_dir().mkdir(parents=True, exist_ok=True)
    user_store = UserStore(Config.users_db_path())
    remembered_login = RememberedLogin(Config.app_dir())

    _active_database: list[Database] = []

    def _show_window(user: "User", window: "MainWindow") -> None:
        """Apply icon, geometry and signals, then show the window."""
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
        window.logout_requested.connect(_session_loop)
        window.database_replaced.connect(lambda: _reload_database(user, window))
        window.full_restore_requested.connect(
            lambda path: _restore_everything(path, window)
        )
        window.database_load_requested.connect(
            lambda path: _load_database(path, user, window)
        )

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
        database = _open_user_database(user.username)
        _active_database.append(database)
        _load_currency(database)
        window = _build_main_window(database, user, user_store)
        _show_window(user, window)
        old_window.deleteLater()

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
        old_window.deleteLater()
        _session_loop()

    def _session_loop() -> None:
        """Run login → main window → (optional) re-login cycle."""
        user = _run_login_flow(user_store, remembered_login)
        if user is None:
            app.quit()
            return

        if _active_database:
            _active_database[0].close()
            _active_database.clear()

        try:
            database = _open_user_database(user.username)
        except sqlite3.DatabaseError as exc:
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
            _session_loop()
            return
        _active_database.append(database)
        _load_currency(database)

        window = _build_main_window(database, user, user_store)
        _show_window(user, window)

    QTimer.singleShot(0, _session_loop)

    result = app.exec()
    if _active_database:
        _active_database[0].close()
    user_store.close()
    return result


if __name__ == "__main__":
    sys.exit(main())
