"""Main application window with tab-based interface."""

import shutil
from datetime import date as _date
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
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
from clear_budget.ui.ui_paths import default_downloads_dir
from clear_budget.shared.db_validation import validate_db
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.views.archive_view import ArchiveView
from clear_budget.ui.views.credit_card_view import CreditCardView
from clear_budget.ui.views.month_view import MonthView
from clear_budget.ui.views.solvency_panel import SolvencyPanel
from clear_budget.ui.widgets.scrollable_tab import ScrollableTab

# GitHub releases page opened by Help > Check for Updates.
RELEASES_URL = "https://github.com/oernster/ClearBudget/releases"


class MainWindow(QMainWindow):
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
        self.apply_theme()

    def init_ui(self) -> None:
        """Build main window with tabs."""
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.tabBar().setExpanding(False)

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
        )
        self.tabs.addTab(self._scrollable(credit_card_view), "Credit Cards")

        archive_view = ArchiveView(self.month_view_model.budget_service)
        self.tabs.addTab(self._scrollable(archive_view), "Archive")

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
        new_budget_action.setEnabled(not self.read_only)

        file_menu.addSeparator()

        import_export_menu = file_menu.addMenu("Import / &Export")

        export_action = import_export_menu.addAction("&Export Database…")
        export_action.triggered.connect(self._on_export_database)

        import_action = import_export_menu.addAction("&Import Database…")
        import_action.triggered.connect(self._on_import_database)
        import_action.setEnabled(not self.read_only)

        if self.current_user.is_admin:
            import_export_menu.addSeparator()

            export_viewer_action = import_export_menu.addAction(
                "Export &Read-Only Viewer Package…"
            )
            export_viewer_action.triggered.connect(self._on_export_viewer_package)

            import_viewer_action = import_export_menu.addAction(
                "&Import Read-Only Viewer Package…"
            )
            import_viewer_action.triggered.connect(self._on_import_viewer_package)

        file_menu.addSeparator()

        prefs_action = file_menu.addAction("&Preferences…")
        prefs_action.triggered.connect(self._on_preferences)
        prefs_action.setEnabled(not self.read_only)

        bank_action = file_menu.addAction("&Bank Account Settings…")
        bank_action.triggered.connect(self._on_bank_account_settings)
        bank_action.setEnabled(not self.read_only)

        file_menu.addSeparator()

        logout_action = file_menu.addAction("&Switch User")
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
        about_action = help_menu.addAction("&About Clear Budget")
        check_updates_action = help_menu.addAction("Check for &Updates")
        how_it_works_action = help_menu.addAction("How It Works")
        licence_action = help_menu.addAction("View Licence (LGPL-3.0)")
        how_it_works_action.triggered.connect(self._on_how_it_works)
        about_action.triggered.connect(self._on_about)
        check_updates_action.triggered.connect(self._on_check_updates)
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
        """Open the GitHub releases page in the default browser."""
        QDesktopServices.openUrl(QUrl(RELEASES_URL))

    def _on_licence(self) -> None:
        from clear_budget.ui.widgets.about_dialog import LicenceDialog

        LicenceDialog(self).exec()

    def _validate_db(self, path: Path) -> str | None:
        """Return an error string if path is not a valid ClearBudget db, else None."""
        return validate_db(path)

    def _on_export_database(self) -> None:
        """Copy the active database to a user-chosen backup location."""
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export Database",
            str(default_downloads_dir() / "clearbudget_backup.db"),
            "Clear Budget Database (*.db)",
        )
        if not dest:
            return
        dest_path = Path(dest)
        if dest_path.suffix.lower() != ".db":
            dest_path = dest_path.with_suffix(".db")
        try:
            shutil.copy2(self.db_path, dest_path)
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle("Export Successful")
            box.setText(f"Database exported to:\n{dest_path}")
            label_w = ui_scale.px(460)
            box.setStyleSheet(f"QLabel#qt_msgbox_label {{ min-width: {label_w}px; }}")
            box.exec()
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def _on_export_viewer_package(self) -> None:
        """Open the dialog to export a read-only viewer package."""
        from clear_budget.ui.widgets.export_viewer_package_dialog import (
            ExportViewerPackageDialog,
        )

        dlg = ExportViewerPackageDialog(self.db_path, parent=self)
        dlg.exec()

    def _on_import_database(self) -> None:
        """Replace the active database with a user-chosen backup file."""
        src, _ = QFileDialog.getOpenFileName(
            self,
            "Import Database",
            str(default_downloads_dir()),
            "Clear Budget Database (*.db)",
        )
        if not src:
            return
        src_path = Path(src)
        if src_path.resolve() == self.db_path.resolve():
            QMessageBox.warning(
                self,
                "Import",
                "Selected file is the active database - nothing to import.",
            )
            return

        has_data = False
        if self.db_path.exists():
            try:
                cursor = self.month_view_model.budget_service.bill_repo.conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM bills")
                has_data = cursor.fetchone()[0] > 0
            except Exception:
                has_data = True

        if has_data:
            reply = QMessageBox.question(
                self,
                "Overwrite Existing Data?",
                "The active database already contains data.\n\n"
                "Importing will permanently replace all bills, income sources, "
                "credit cards, "
                "overrides and settings with the contents of the selected file.\n\n"
                "This cannot be undone. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        validation_error = self._validate_db(src_path)
        if validation_error:
            QMessageBox.critical(
                self,
                "Invalid Database",
                f"Cannot import - invalid Clear Budget database.\n\n{validation_error}",
            )
            return

        try:
            shutil.copy2(src_path, self.db_path)
            self.database_replaced.emit()
        except OSError as exc:
            QMessageBox.critical(self, "Import Failed", str(exc))

    def apply_theme(self) -> None:
        """Build status bar and menus (theme applied app-wide via QApplication)."""
        self._build_status_bar()
        self._build_menus()
