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


def _acquire_single_instance_mutex():
    """Return a Windows mutex handle, or None if another instance is running."""
    handle = ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.kernel32.CloseHandle(handle)
        return None
    return handle


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

    _mutex = _acquire_single_instance_mutex()
    if _mutex is None:
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
        _restore_w = int(_avail_w * 0.88)
        _restore_h = int(_avail_h * 0.88)
        _restore_x = _avail.x() + (_avail_w - _restore_w) // 2
        _restore_y = _avail.y() + (_avail_h - _restore_h) // 2
        window.setGeometry(_restore_x, _restore_y, _restore_w, _restore_h)
        window.showMaximized()
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
