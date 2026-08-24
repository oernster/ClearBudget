"""Main application window with tab-based interface."""

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from clear_budget.auth.models import User
from clear_budget.auth.user_store import UserStore
from clear_budget.ui import ui_scale
from clear_budget.ui._main_window_account import MainWindowAccountMixin
from clear_budget.ui._main_window_menus import MainWindowMenuMixin
from clear_budget.ui._main_window_nav import MainWindowNavMixin
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.views.archive_view import ArchiveView
from clear_budget.ui.views.credit_card_view import CreditCardView
from clear_budget.ui.views.month_view import MonthView
from clear_budget.ui.views.solvency_panel import SolvencyPanel
from clear_budget.ui.update_check import UpdateCheckController
from clear_budget.ui.utils.tab_icons import mark_current_tab
from clear_budget.ui.widgets.scrollable_tab import ScrollableTab

if TYPE_CHECKING:
    from clear_budget.application.services.update_service import UpdateService

# Fire the day-rollover fold slightly after local midnight so date.today()
# has definitely advanced when the handler runs.
_MIDNIGHT_FOLD_BUFFER_MS = 2000


class MainWindow(
    MainWindowAccountMixin, MainWindowMenuMixin, MainWindowNavMixin, QMainWindow
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
        title = f"ClearBudget - {current_user.username}"
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
        # The bar is HIDDEN and stays that way. The four tabs are icon buttons
        # in each view's navigation tray, so a strip above them would be a
        # second, empty copy of the same control. The QTabWidget is kept for
        # what it is actually good at, owning the pages and switching between
        # them; nothing styles or navigates the bar, because nobody sees it.
        self.tabs.tabBar().hide()

        month_view = MonthView(self.month_view_model, read_only=self.read_only)
        self.tabs.addTab(self._scrollable(month_view), "Monthly Budget")

        solvency_panel = SolvencyPanel(
            self.solvency_view_model,
            read_only=self.read_only,
            base_month=self.month_view_model.base_month,
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
            _tray_view.budgets_btn.clicked.connect(self._on_manage_budgets)
            _tray_view.users_btn.clicked.connect(self._on_users)
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
        # The card panels and the six-month strip are driven by the month's
        # bills, which are edited on a DIFFERENT tab, so they need the same
        # summary signal Solvency already takes. Without it the Credit Cards
        # tab showed whatever was true when the window was built.
        self.month_view_model.month_summary_updated.connect(
            credit_card_view.on_month_summary_updated
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

        _views = [month_view, solvency_panel, credit_card_view, archive_view]
        self._wire_tab_buttons(_views)
        self._setup_keyboard_nav(_views)

    @staticmethod
    def _scrollable(widget: QWidget) -> ScrollableTab:
        return ScrollableTab(widget)

    def _wire_tab_buttons(self, views: list) -> None:
        """Point every view's tab buttons at the pages and keep them in step.

        Every view carries its OWN four buttons, because every view builds its
        own tray. They all drive the one QTabWidget; every set is marked
        together on each switch, so the tab you are on is marked whichever
        tray you happen to be looking at.
        """
        for view in views:
            for index, button in enumerate(view.tab_btns):
                button.clicked.connect(
                    lambda _checked=False, target=index: self.tabs.setCurrentIndex(
                        target
                    )
                )
        self._tab_button_sets = [view.tab_btns for view in views]
        self.tabs.currentChanged.connect(self._mark_current_tab)
        self._mark_current_tab(self.tabs.currentIndex())

    def _mark_current_tab(self, index: int) -> None:
        """Mark `index` as current on every view's copy of the tab buttons."""
        for buttons in self._tab_button_sets:
            mark_current_tab(buttons, index)

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

        source = run_load_flow(self, self.db_path, self._live_connection())
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
