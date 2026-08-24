"""Main application window with tab-based interface."""

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QMainWindow

from clear_budget.auth.models import User
from clear_budget.auth.user_store import UserStore
from clear_budget.ui import ui_scale
from clear_budget.ui._main_window_account import MainWindowAccountMixin
from clear_budget.ui._main_window_menus import MainWindowMenuMixin
from clear_budget.ui._main_window_nav import MainWindowNavMixin
from clear_budget.ui._main_window_tabs import MainWindowTabsMixin
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.update_check import UpdateCheckController

if TYPE_CHECKING:
    from clear_budget.application.services.update_service import UpdateService

# Fire the day-rollover fold slightly after local midnight so date.today()
# has definitely advanced when the handler runs.
_MIDNIGHT_FOLD_BUFFER_MS = 2000


class MainWindow(
    MainWindowAccountMixin,
    MainWindowMenuMixin,
    MainWindowNavMixin,
    MainWindowTabsMixin,
    QMainWindow,
):
    """Application main window with tabbed views."""

    # Emitted to SUSPEND this session and offer the sign-in screen. The
    # window is only hidden and its database stays open, so a cancelled
    # sign-in comes back to it.
    switch_user_requested = Signal()
    # Emitted to END this session. The window is destroyed and the database
    # closed, so there is nothing to come back to and a cancelled sign-in
    # closes the application. Nothing is lost either way: the budget is on
    # disk; both routes lead to the same sign-in screen.
    sign_out_requested = Signal()
    # Emitted after a database import - signals main to reload without restart.
    database_replaced = Signal()
    # Emitted with a validated full-backup zip path. Only main.py can act on
    # it: the open databases must close before the files can be replaced and
    # the session returns to the sign-in screen afterwards.
    full_restore_requested = Signal(str)
    database_load_requested = Signal(str)

    def __init__(
        self,
        month_view_model: MonthViewModel,
        solvency_view_model: SolvencyViewModel,
        current_user: User,
        user_store: UserStore,
        db_path: Path,
        update_service: "UpdateService",
    ) -> None:
        """Initialize main window and tabs."""
        super().__init__()
        self.month_view_model = month_view_model
        self.solvency_view_model = solvency_view_model
        self.current_user = current_user
        self.user_store = user_store
        self.db_path = db_path
        self.read_only = current_user.is_read_only
        # The account is NOT in the title any more. It was a few pixels of
        # system chrome naming whose budget was on screen, which is the one
        # thing a shared machine most needs to be sure of; it is now shown at
        # the left of every tab's month tray, in the size the month is.
        self.setWindowTitle("ClearBudget")
        self.setMinimumSize(ui_scale.px(900), ui_scale.px(580))
        self.init_ui()
        self._build_window_chrome()
        # Parented to the window so it stops firing once the window is gone.
        self._midnight_timer = QTimer(self)
        self._midnight_timer.setSingleShot(True)
        self._midnight_timer.timeout.connect(self._on_midnight_fold)
        self._schedule_midnight_fold()
        # Owns the launch, daily and manual update checks; prompts on a newer
        # published release.
        self._update_controller = UpdateCheckController(update_service, self)

    def _schedule_midnight_fold(self) -> None:
        """Arm the timer for just after the next local midnight."""
        from datetime import datetime, timedelta

        # Local wall-clock on purpose: the fold happens at the user's midnight.
        now = datetime.now()  # noqa: DTZ005 (local midnight is the point)
        next_midnight = datetime.combine(
            now.date() + timedelta(days=1), datetime.min.time()
        )
        delay_ms = int((next_midnight - now).total_seconds() * 1000)
        self._midnight_timer.start(delay_ms + _MIDNIGHT_FOLD_BUFFER_MS)

    def _on_midnight_fold(self) -> None:
        """Apply bank bills/income that fell due at midnight, then re-arm."""
        self.month_view_model.budget_service.apply_elapsed_bank_transactions()
        self.month_view_model.refresh_month_summary()
        self._schedule_midnight_fold()

    def _on_new_budget(self) -> None:
        """Create a named empty budget alongside the current one and open it.

        Creating never destroys. This used to be a double-confirmed wipe
        because a user could own only one budget, so an empty one could only
        be had by emptying theirs; a user can now own several.
        """
        from clear_budget.ui.widgets._budgets_flow import run_new_budget_flow

        if run_new_budget_flow(self, self.current_user.username):
            self.database_replaced.emit()

    def _on_manage_budgets(self) -> None:
        """Open the budget manager; reload when the active budget changed."""
        from clear_budget.ui.widgets._budgets_flow import run_budgets_flow

        if run_budgets_flow(self, self.current_user.username):
            self.database_replaced.emit()

    def _on_preferences(self) -> None:
        """Open currency preferences dialog; rebuild window on change."""
        from clear_budget.ui.widgets._preferences_flow import run_preferences_flow

        conn = self.month_view_model.budget_service.bill_repo.conn
        if run_preferences_flow(self, conn):
            self.database_replaced.emit()

    def _on_bank_account_settings(self) -> None:
        """Open the overdraft facility settings dialog."""
        from clear_budget.ui.widgets._bank_account_settings_flow import (
            run_bank_account_settings_flow,
        )

        run_bank_account_settings_flow(self, self.month_view_model.budget_service)
        self.month_view_model.refresh_month_summary()

    def _on_how_it_works(self) -> None:
        from clear_budget.ui.widgets.how_it_works_dialog import HowItWorksDialog

        HowItWorksDialog(self).exec()

    def _on_about(self) -> None:
        from clear_budget.ui.widgets.about_dialog import AboutDialog

        AboutDialog(self).exec()

    def _on_check_updates(self) -> None:
        """Run a real update check and report the outcome."""
        self._update_controller.check_manually()

    def _on_licence(self) -> None:
        from clear_budget.ui.widgets.about_dialog import LicenceDialog

        LicenceDialog(self).exec()

    def _on_save_database(self) -> None:
        """Save the database to the remembered location (first time: Save As)."""
        from clear_budget.ui.widgets._save_load_flow import run_save_flow

        run_save_flow(self, self._live_connection())

    def _on_save_as_database(self) -> None:
        """Prompt for a save file, remember it, then save the database."""
        from clear_budget.ui.widgets._save_load_flow import run_save_as_flow

        run_save_as_flow(self, self._live_connection())

    def _live_connection(self):
        """The session's open SQLite connection, for a consistent snapshot."""
        return self.month_view_model.budget_service.bill_repo.conn

    def _on_load_database(self) -> None:
        """Choose a database to load and hand the ACT to the composition root.

        The window does not put the file in place itself. This database is
        open; replacing an open database underneath its own connection
        destroyed two real budgets: the file was swapped while the
        connection carried on writing against what it thought was there;
        what survived was the right length and entirely zero bytes.
        Only `main.py` can close the connection first, so only `main.py`
        may do the replacing.
        """
        from clear_budget.ui.widgets._save_load_flow import run_load_flow

        source = run_load_flow(
            self,
            self.db_path,
            self._live_connection(),
            self.current_user.username,
            self.user_store,
        )
        if source is not None:
            self.database_load_requested.emit(str(source))

    def _on_backup_everything(self) -> None:
        """Write every account and every budget into one backup zip."""
        from clear_budget.ui.widgets._full_backup_flow import backup_everything

        backup_everything(self)

    def _on_restore_everything(self) -> None:
        """Validate and double-confirm a full restore, then hand it to main."""
        from clear_budget.ui.widgets._full_backup_flow import restore_everything

        restore_everything(self)

    def _build_window_chrome(self) -> None:
        """Build the status bar and menus.

        Named for what it does: the THEME is applied app-wide on the
        QApplication by clear_budget.ui.theme, not here.
        """
        self._build_status_bar()
        self._build_menus()
