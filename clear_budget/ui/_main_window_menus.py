"""Menu-bar and status-bar construction for MainWindow.

Extracted from main_window.py as a mixin to keep that module under the 400-LOC
limit (enforced by tests/structural/test_loc_limits.py). The menu action
handlers stay on MainWindow; this mixin only builds the bars and wires them to
those handlers via self.
"""

from datetime import date as _date

from PySide6.QtWidgets import QLabel

from clear_budget.ui import ui_scale


class MainWindowMenuMixin:
    """Builds the status bar and the File/Users/Help menus for MainWindow."""

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
