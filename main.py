"""Application entry point - composition root and Qt event loop."""

import sys
import ctypes
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon

from clear_budget.shared.config import Config
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
from clear_budget.ui.main_window import MainWindow
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel


def _find_runtime_icon() -> Path | None:
    """Locate runtime PNG icon beside the executable.

    Qt sometimes fails to decode ICO files in frozen apps, so we use PNG.
    """
    icon_path = Path(sys.executable).resolve().parent / "clearbudget_256.png"
    if icon_path.exists():
        return icon_path
    return None


_MUTEX_NAME = "Global\\ClearBudget_SingleInstance"


def _acquire_single_instance_mutex():
    """Return a Windows mutex handle, or None if another instance is running."""
    handle = ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.kernel32.CloseHandle(handle)
        return None
    return handle


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
    # Scale factor: reference design is 1260px tall. Cap at 1.5 so 4K doesn't produce enormous UI.
    ui_scale.init(min(_avail_h / 1260.0, 1.5))

    icon_path = _find_runtime_icon()
    if icon_path:
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            app.setWindowIcon(icon)

    config = Config.default()
    config.ensure_directories()

    database = Database(config.db_path)
    database.connect()
    database.create_schema()

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

    month_view_model = MonthViewModel(budget_service=budget_service)
    solvency_view_model = SolvencyViewModel(budget_service=budget_service)

    window = MainWindow(
        month_view_model=month_view_model,
        solvency_view_model=solvency_view_model,
    )

    if icon_path:
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            window.setWindowIcon(icon)

    # Set restored geometry to 88% of available screen, centred.
    # Qt uses this size when the user un-maximises, ensuring it always fits on screen.
    _restore_w = int(_avail_w * 0.88)
    _restore_h = int(_avail_h * 0.88)
    _restore_x = _avail.x() + (_avail_w - _restore_w) // 2
    _restore_y = _avail.y() + (_avail_h - _restore_h) // 2
    window.setGeometry(_restore_x, _restore_y, _restore_w, _restore_h)
    window.showMaximized()

    result = app.exec()
    database.close()
    return result


if __name__ == "__main__":
    sys.exit(main())
