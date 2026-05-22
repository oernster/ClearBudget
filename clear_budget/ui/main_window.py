"""Main application window with tab-based interface."""

from datetime import date as _date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QLabel,
    QWidget,
)

from clear_budget.auth.models import User
from clear_budget.auth.user_store import UserStore
from clear_budget.ui import ui_scale
from clear_budget.ui.dark_theme import get_dark_qss
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.views.archive_view import ArchiveView
from clear_budget.ui.views.credit_card_view import CreditCardView
from clear_budget.ui.views.month_view import MonthView
from clear_budget.ui.views.solvency_panel import SolvencyPanel
from clear_budget.ui.widgets.scrollable_tab import ScrollableTab


class MainWindow(QMainWindow):
    """Application main window with tabbed views."""

    # Emitted when the user requests logout (lock screen) or switch user.
    logout_requested = Signal()
    # Emitted after a database import — signals main to reload without restart.
    database_replaced = Signal()

    def __init__(
        self,
        month_view_model: MonthViewModel,
        solvency_view_model: SolvencyViewModel,
        current_user: User,
        user_store: UserStore,
    ) -> None:
        """Initialize main window and tabs."""
        super().__init__()
        self.month_view_model = month_view_model
        self.solvency_view_model = solvency_view_model
        self.current_user = current_user
        self.user_store = user_store
        self.setWindowTitle(f"ClearBudget — {current_user.username}")
        self.setMinimumSize(ui_scale.px(900), ui_scale.px(580))
        self.init_ui()
        self.apply_theme()

    def init_ui(self) -> None:
        """Build main window with tabs."""
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.tabBar().setExpanding(False)

        month_view = MonthView(self.month_view_model)
        self.tabs.addTab(self._scrollable(month_view), "Monthly Budget")

        solvency_panel = SolvencyPanel(self.solvency_view_model)
        self.tabs.addTab(self._scrollable(solvency_panel), "Solvency")

        credit_card_view = CreditCardView(
            self.month_view_model.budget_service,
            self.month_view_model.current_month,
        )
        self.tabs.addTab(self._scrollable(credit_card_view), "Credit Cards")

        archive_view = ArchiveView(self.month_view_model.budget_service)
        self.tabs.addTab(self._scrollable(archive_view), "Archive")
        archive_view.database_replaced.connect(self.database_replaced)

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

        self.month_view_model.month_changed.connect(
            lambda ym: solvency_panel.prev_btn.setEnabled(
                ym > self.month_view_model.base_month
            )
        )
        self.month_view_model.month_changed.connect(
            lambda ym: credit_card_view.prev_btn.setEnabled(
                ym > self.month_view_model.base_month
            )
        )

        at_base = (
            self.month_view_model.current_month <= self.month_view_model.base_month
        )
        solvency_panel.prev_btn.setEnabled(not at_base)
        credit_card_view.prev_btn.setEnabled(not at_base)

        if self.month_view_model.month_summary:
            self.solvency_view_model.update_month_summary(
                self.month_view_model.month_summary
            )

    def _build_status_bar(self) -> None:
        today = _date.today().strftime("%A, %d %B %Y")
        lbl = QLabel(f"  Today: {today}  ")
        lbl.setStyleSheet(
            ui_scale.style(
                "font-size: 18px; font-weight: bold; color: #00d4ff; padding: 2px 8px;"
            )
        )
        self.statusBar().addPermanentWidget(lbl)
        self.statusBar().setStyleSheet(
            "QStatusBar { background-color: #0d0d1a; border-top: 1px solid #1e3a5f; }"
        )

    @staticmethod
    def _scrollable(widget: QWidget) -> ScrollableTab:
        return ScrollableTab(widget)

    def _build_menus(self) -> None:
        """Build File and Help menu bar."""
        # File menu
        file_menu = self.menuBar().addMenu("&File")

        new_budget_action = file_menu.addAction("&New Budget…")
        new_budget_action.triggered.connect(self._on_new_budget)

        file_menu.addSeparator()

        logout_action = file_menu.addAction("&Lock / Switch User")
        logout_action.triggered.connect(self._on_logout)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        # Users menu (admin only)
        if self.current_user.is_admin:
            users_menu = self.menuBar().addMenu("&Users")
            manage_action = users_menu.addAction("&Manage Users…")
            manage_action.triggered.connect(self._on_manage_users)

        # Help menu
        help_menu = self.menuBar().addMenu("&Help")
        about_action = help_menu.addAction("&About ClearBudget")
        licence_action = help_menu.addAction("View Licence (LGPL-3.0)")
        about_action.triggered.connect(self._on_about)
        licence_action.triggered.connect(self._on_licence)

    def _on_new_budget(self) -> None:
        """Wipe all budget data after double-confirmation."""
        first = QMessageBox.question(
            self,
            "New Budget",
            "This will permanently delete ALL bills, income sources, credit cards,\n"
            "overrides, and settings for this user.\n\n"
            "This cannot be undone.  Are you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if first != QMessageBox.StandardButton.Yes:
            return
        second = QMessageBox.question(
            self,
            "New Budget — Final Confirmation",
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

    def _on_logout(self) -> None:
        """Lock the screen and return to login."""
        self.logout_requested.emit()
        self.hide()

    def _on_manage_users(self) -> None:
        from clear_budget.ui.widgets.user_management_dialog import UserManagementDialog

        dlg = UserManagementDialog(self.user_store, self.current_user, parent=self)
        dlg.exec()

    def _on_about(self) -> None:
        from clear_budget.ui.widgets.about_dialog import AboutDialog

        AboutDialog(self).exec()

    def _on_licence(self) -> None:
        from clear_budget.ui.widgets.about_dialog import LicenceDialog

        LicenceDialog(self).exec()

    def apply_theme(self) -> None:
        """Apply dark theme stylesheet."""
        self.setStyleSheet(get_dark_qss())
        self._build_status_bar()
        self._build_menus()
