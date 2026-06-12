"""Application entry point - composition root and Qt event loop.

Handles the full login lifecycle:
1. Open central users store.
2. If no users exist → first-run CreateUserDialog.
3. Show LoginDialog.
4. On success, open that user's budget database and show MainWindow.
5. On MainWindow.logout_requested → close window, loop back to step 3.
"""

import sys
import ctypes
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon

from clear_budget.shared.config import Config
from clear_budget.auth.user_store import UserStore
from clear_budget.auth.models import User
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.shared.currency import set_currency
from clear_budget.ui.dark_theme import get_dark_qss
from clear_budget.ui.main_window import MainWindow
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel


def _find_runtime_icon() -> Path | None:
    """Locate runtime PNG icon.

    Checks beside the executable first (installed/frozen), then falls back
    to the project root beside main.py (dev mode).
    """
    beside_exe = Path(sys.executable).resolve().parent / "clearbudget_256.png"
    if beside_exe.exists():
        return beside_exe
    beside_main = Path(__file__).resolve().parent / "clearbudget_256.png"
    return beside_main if beside_main.exists() else None


_MUTEX_NAME = "Global\\ClearBudget_SingleInstance"
_LOCK_FILENAME = "clearbudget.lock"

# Win32 GetLastError code returned by CreateMutexW when the named mutex already
# exists (i.e. another instance is running).
_WIN_ERROR_ALREADY_EXISTS = 183

# Default main-window geometry, expressed as a fraction of the available screen
# area.  The fractions keep the window compact on large monitors (e.g. a 34in
# widescreen); the minimum floors below guarantee the multi-column Bills/Income
# tables stay readable on small displays such as a 13in MacBook.
_WINDOW_WIDTH_FRACTION = 0.33
_WINDOW_HEIGHT_FRACTION = 0.92

# Absolute floors in logical screen points (device-independent, so NOT scaled by
# the UI factor).  These bind only on small screens where the fractional size
# would clip table columns; on large screens the fractions already exceed them
# and the window keeps its compact proportions.  Both are always capped to the
# available screen area so the window never exceeds the display.
_MIN_WINDOW_WIDTH_PT = 860
_MIN_WINDOW_HEIGHT_PT = 780


def _acquire_single_instance_lock():
    """Acquire a single-instance lock for this process.

    Returns an opaque handle that the caller must keep alive for the lifetime
    of the application; the lock is released automatically when the process
    exits or the handle is dropped.  Returns None if another instance already
    holds the lock.

    Windows uses a named kernel mutex.  POSIX platforms (macOS, Linux) use an
    exclusive advisory lock on a file in the application directory, since
    ctypes.windll exists only on Windows.
    """
    if sys.platform == "win32":
        handle = ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)
        if ctypes.windll.kernel32.GetLastError() == _WIN_ERROR_ALREADY_EXISTS:
            ctypes.windll.kernel32.CloseHandle(handle)
            return None
        return handle

    import fcntl

    Config.app_dir().mkdir(parents=True, exist_ok=True)
    lock_file = open(Config.app_dir() / _LOCK_FILENAME, "w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        return None
    return lock_file


def _run_login_flow(user_store: UserStore) -> User | None:
    """Show first-run or login dialog.  Returns authenticated User or None (quit)."""
    from clear_budget.ui.widgets.create_user_dialog import CreateUserDialog
    from clear_budget.ui.widgets.login_dialog import LoginDialog

    if not user_store.has_users():
        dlg = CreateUserDialog(user_store, is_first_user=True)
        if dlg.exec() != CreateUserDialog.Accepted or dlg.created_user is None:
            return None
        # First user just created - log them in directly.
        return dlg.created_user

    dlg = LoginDialog(user_store)
    if dlg.exec() != LoginDialog.Accepted:
        return None
    return dlg.authenticated_user


def _open_user_database(username: str) -> Database:
    """Open (or create) the budget database for username."""
    config = Config.for_user(username)
    config.ensure_directories()
    database = Database(config.db_path)
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
    month_view_model = MonthViewModel(budget_service=budget_service)
    solvency_view_model = SolvencyViewModel(budget_service=budget_service)
    return MainWindow(
        month_view_model=month_view_model,
        solvency_view_model=solvency_view_model,
        current_user=current_user,
        user_store=user_store,
        db_path=database.db_path,
    )


def main() -> int:
    """Initialize application and start event loop."""
    app = QApplication([])

    _instance_lock = _acquire_single_instance_lock()
    if _instance_lock is None:
        QMessageBox.warning(None, "ClearBudget", "ClearBudget is already running.")
        return 1

    from clear_budget.ui import ui_scale

    _screen = app.primaryScreen()
    _avail = _screen.availableGeometry()
    _avail_h = _avail.height()
    _avail_w = _avail.width()
    ui_scale.init(min(_avail_h / 1260.0, 1.5))

    icon_path = _find_runtime_icon()
    if icon_path:
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            app.setWindowIcon(icon)

    app.setStyleSheet(get_dark_qss())

    Config.app_dir().mkdir(parents=True, exist_ok=True)
    user_store = UserStore(Config.users_db_path())

    _active_database: list[Database] = []

    def _show_window(user: "User", window: "MainWindow") -> None:
        """Apply icon, geometry, signals, and show window."""
        if icon_path:
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                window.setWindowIcon(icon)
        _restore_w = min(
            max(int(_avail_w * _WINDOW_WIDTH_FRACTION), _MIN_WINDOW_WIDTH_PT),
            _avail_w,
        )
        _restore_h = min(
            max(int(_avail_h * _WINDOW_HEIGHT_FRACTION), _MIN_WINDOW_HEIGHT_PT),
            _avail_h,
        )
        _restore_x = _avail.x() + (_avail_w - _restore_w) // 2
        _restore_y = _avail.y() + (_avail_h - _restore_h) // 2
        window.setGeometry(_restore_x, _restore_y, _restore_w, _restore_h)
        window.show()
        window.logout_requested.connect(_session_loop)
        window.database_replaced.connect(lambda: _reload_database(user, window))

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

    def _session_loop() -> None:
        """Run login → main window → (optional) re-login cycle."""
        user = _run_login_flow(user_store)
        if user is None:
            app.quit()
            return

        if _active_database:
            _active_database[0].close()
            _active_database.clear()

        database = _open_user_database(user.username)
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
