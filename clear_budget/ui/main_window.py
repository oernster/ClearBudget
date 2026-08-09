"""Main application window with tab-based interface."""

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from clear_budget.auth.models import User
from clear_budget.auth.user_store import UserStore
from clear_budget.ui import ui_scale
from clear_budget.ui._main_window_menus import MainWindowMenuMixin
from clear_budget.ui._main_window_nav import MainWindowNavMixin
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.views.archive_view import ArchiveView
from clear_budget.ui.views.credit_card_view import CreditCardView
from clear_budget.ui.views.month_view import MonthView
from clear_budget.ui.views.solvency_panel import SolvencyPanel
from clear_budget.ui.update_check import UpdateCheckController
from clear_budget.ui.widgets.nav_tab_bar import NavTabBar
from clear_budget.ui.widgets.scrollable_tab import ScrollableTab

if TYPE_CHECKING:
    from clear_budget.application.services.update_service import UpdateService

# Fire the day-rollover fold slightly after local midnight so date.today()
# has definitely advanced when the handler runs.
_MIDNIGHT_FOLD_BUFFER_MS = 2000


class MainWindow(MainWindowMenuMixin, MainWindowNavMixin, QMainWindow):
    """Application main window with tabbed views."""

    # Emitted when the user switches account.
    logout_requested = Signal()
    # Emitted after a database import - signals main to reload without restart.
    database_replaced = Signal()

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
        title = f"Clear Budget - {current_user.username}"
        if self.read_only:
            title += " (Read-only)"
        self.setWindowTitle(title)
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

    def init_ui(self) -> None:
        """Build main window with tabs."""
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        # A tab bar whose keyboard cursor is separate from its selection, so
        # stepping the focus ring into the strip never switches tab.
        self.tabs.setTabBar(NavTabBar())
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.tabBar().setExpanding(False)
        # The tabs are styled as detached pills, so Qt's base line under the
        # whole bar would read as a stray rule (it ignores QSS drawBase).
        self.tabs.tabBar().setDrawBase(False)

        month_view = MonthView(self.month_view_model, read_only=self.read_only)
        self.tabs.addTab(self._scrollable(month_view), "Monthly Budget")

        solvency_panel = SolvencyPanel(
            self.solvency_view_model, read_only=self.read_only
        )
        self.tabs.addTab(self._scrollable(solvency_panel), "Solvency")

        credit_card_view = CreditCardView(
            self.month_view_model.budget_service,
            self.month_view_model.current_month,
            read_only=self.read_only,
            base_month=self.month_view_model.base_month,
        )
        self.tabs.addTab(self._scrollable(credit_card_view), "Credit Cards")

        archive_view = ArchiveView(
            self.month_view_model.budget_service, read_only=self.read_only
        )
        self.tabs.addTab(self._scrollable(archive_view), "Archive")

        # Every tray carries the same icon shortcuts; all of them drive the
        # same window-level flows their menu items do.
        for _tray_view in (month_view, solvency_panel, credit_card_view, archive_view):
            _tray_view.save_btn.clicked.connect(self._on_save_database)
            _tray_view.load_btn.clicked.connect(self._on_load_database)
            _tray_view.settings_btn.clicked.connect(self._on_preferences)
            _tray_view.bank_btn.clicked.connect(self._on_bank_account_settings)
            _tray_view.info_btn.clicked.connect(self._on_how_it_works)

        layout.addWidget(self.tabs)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.month_view_model.month_changed.connect(self.solvency_view_model.set_month)
        self.month_view_model.month_changed.connect(credit_card_view.set_month)
        self.month_view_model.month_summary_updated.connect(
            self.solvency_view_model.update_month_summary
        )

        solvency_panel.prev_btn.clicked.connect(self.month_view_model.previous_month)
        solvency_panel.next_btn.clicked.connect(self.month_view_model.next_month)
        credit_card_view.prev_btn.clicked.connect(self.month_view_model.previous_month)
        credit_card_view.next_btn.clicked.connect(self.month_view_model.next_month)

        for _nav in (solvency_panel, credit_card_view):
            self.month_view_model.month_changed.connect(
                lambda ym, b=_nav.prev_btn: b.setEnabled(
                    ym > self.month_view_model.base_month
                )
            )

        at_base = (
            self.month_view_model.current_month <= self.month_view_model.base_month
        )
        solvency_panel.prev_btn.setEnabled(not at_base)
        credit_card_view.prev_btn.setEnabled(not at_base)

        # Solvency owns the nav-label health colour; mirror it onto every tab.
        for _view in (month_view, credit_card_view, archive_view):
            solvency_panel.month_label_color_changed.connect(_view.set_nav_label_color)

        if self.month_view_model.month_summary:
            self.solvency_view_model.update_month_summary(
                self.month_view_model.month_summary
            )

        self._setup_keyboard_nav(
            [month_view, solvency_panel, credit_card_view, archive_view]
        )

    @staticmethod
    def _scrollable(widget: QWidget) -> ScrollableTab:
        return ScrollableTab(widget)

    def _on_new_budget(self) -> None:
        """Wipe all budget data after double-confirmation."""
        first = QMessageBox.question(
            self,
            "New Budget",
            "This will permanently delete ALL bills, income sources, credit cards,\n"
            "overrides and settings for this user.\n\n"
            "This cannot be undone.  Are you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if first != QMessageBox.StandardButton.Yes:
            return
        second = QMessageBox.question(
            self,
            "New Budget - Final Confirmation",
            "Really wipe everything and start fresh?\n\n" "Last chance to cancel.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if second == QMessageBox.StandardButton.Yes:
            self.month_view_model.budget_service.reset_all_data()
            self.month_view_model.refresh_month_summary()
            QMessageBox.information(
                self,
                "New Budget",
                "Budget data wiped.  You can now enter your new bills and income.",
            )

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

    def _on_logout(self) -> None:
        """Return to login to switch user."""
        self.logout_requested.emit()
        self.hide()

    def _on_manage_users(self) -> None:
        from clear_budget.ui.widgets.user_management_dialog import UserManagementDialog

        dlg = UserManagementDialog(self.user_store, self.current_user, parent=self)
        dlg.exec()

    def _on_import_viewer_package(self) -> None:
        from clear_budget.ui.widgets._viewer_package_import_flow import (
            run_import_viewer_package_flow,
        )

        user = run_import_viewer_package_flow(self, self.user_store)
        if user is None:
            return
        QMessageBox.information(
            self,
            "Import Successful",
            f"Viewer account '{user.username}' is ready.\n\n"
            "They can sign in with the password from the export.",
        )

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

        run_save_flow(self, self.db_path)

    def _on_save_as_database(self) -> None:
        """Prompt for a save file, remember it, then save the database."""
        from clear_budget.ui.widgets._save_load_flow import run_save_as_flow

        run_save_as_flow(self, self.db_path)

    def _on_load_database(self) -> None:
        """Replace the active database from a user-chosen save file."""
        from clear_budget.ui.widgets._save_load_flow import run_load_flow

        conn = self.month_view_model.budget_service.bill_repo.conn
        if run_load_flow(self, self.db_path, conn):
            self.database_replaced.emit()

    def _on_export_viewer_package(self) -> None:
        """Open the dialog to export a read-only viewer package."""
        from clear_budget.ui.widgets.export_viewer_package_dialog import (
            ExportViewerPackageDialog,
        )

        dlg = ExportViewerPackageDialog(self.db_path, parent=self)
        dlg.exec()

    def _build_window_chrome(self) -> None:
        """Build the status bar and menus.

        Named for what it does: the THEME is applied app-wide on the
        QApplication by clear_budget.ui.theme, not here.
        """
        self._build_status_bar()
        self._build_menus()
