"""Application entry point - composition root and Qt event loop.

Handles the full login lifecycle:
1. Open central users store.
2. If no users exist → first-run CreateUserDialog.
3. Show LoginDialog.
4. On success, open that user's budget database and show MainWindow.
5. On MainWindow.logout_requested → close window, loop back to step 3.
"""

import ctypes
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
from clear_budget.shared.config import Config
from clear_budget.shared.currency import set_currency
from clear_budget.ui._window_geometry import default_window_rect
from clear_budget.version import __version__
from clear_budget.ui.main_window import MainWindow
from clear_budget.ui.theme import apply_theme, load_saved_theme
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

# Reference available-screen height (logical points) that maps to a 1.0x UI scale.
# Taller screens scale the UI up to the cap below; shorter screens scale it down,
# so the layout stays proportionate from a 13in laptop to a 4K display.
_UI_SCALE_REFERENCE_HEIGHT_PT = 1260.0

# Upper bound on the UI scale factor.  Caps growth on tall/4K displays; the lower
# bound (0.5x) is enforced inside ui_scale.init().
_MAX_UI_SCALE_FACTOR = 1.5

# Index of the height element in an (x, y, width, height) screen rect.
_AVAILABLE_HEIGHT = 3


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
    # Deliberately not a context manager: the handle must stay open for the
    # process lifetime, since closing it releases the flock.
    lock_file = open(  # noqa: SIM115 (lock held until exit)
        Config.app_dir() / _LOCK_FILENAME, "w"
    )
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        return None
    return lock_file


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
    app = QApplication([])

    _instance_lock = _acquire_single_instance_lock()
    if _instance_lock is None:
        QMessageBox.warning(None, "ClearBudget", "ClearBudget is already running.")
        return 1

    from clear_budget.ui import launch_screen, ui_scale

    # Resolve the monitor the app was started from before anything is shown,
    # so every window this session opens lands there rather than on whichever
    # display happens to be primary.
    launch_screen.init()
    _avail = launch_screen.available()
    _avail_h = _avail[_AVAILABLE_HEIGHT]
    ui_scale.init(min(_avail_h / _UI_SCALE_REFERENCE_HEIGHT_PT, _MAX_UI_SCALE_FACTOR))

    icon_path = _find_runtime_icon()
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
                width_fraction=_WINDOW_WIDTH_FRACTION,
                height_fraction=_WINDOW_HEIGHT_FRACTION,
                min_width=_MIN_WINDOW_WIDTH_PT,
                min_height=_MIN_WINDOW_HEIGHT_PT,
            )
        )
        window.show()
        launch_screen.centre(window)
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
        user = _run_login_flow(user_store, remembered_login)
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
