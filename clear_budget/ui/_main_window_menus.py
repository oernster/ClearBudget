"""Menu-bar and status-bar construction for MainWindow.

Extracted from main_window.py as a mixin to keep that module under the 400-LOC
limit (enforced by tests/structural/test_loc_limits.py). The menu action
handlers stay on MainWindow; this mixin only builds the bars and wires them to
those handlers via self.
"""

from datetime import date as _date

from PySide6.QtWidgets import QLabel


class MainWindowMenuMixin:
    """Builds the status bar and the File/Users/Help menus for MainWindow."""

    def _build_status_bar(self) -> None:
        today = _date.today().strftime("%A, %d %B %Y")  # noqa: DTZ011 (local date)
        lbl = QLabel(f"  Today: {today}  ")
        # Styled by the theme QSS (QLabel#StatusDateLabel and QStatusBar), so
        # the bar follows the active theme instead of a baked-in dark style.
        lbl.setObjectName("StatusDateLabel")
        self.statusBar().addPermanentWidget(lbl)

    def _build_menus(self) -> None:
        """Build File and Help menu bar."""
        # File menu
        file_menu = self.menuBar().addMenu("&File")

        new_budget_action = file_menu.addAction("&New Budget…")
        new_budget_action.triggered.connect(self._on_new_budget)

        budgets_action = file_menu.addAction("S&witch Budget…")
        budgets_action.triggered.connect(self._on_manage_budgets)

        file_menu.addSeparator()

        load_action = file_menu.addAction("&Load…")
        load_action.triggered.connect(self._on_load_database)

        save_action = file_menu.addAction("&Save")
        save_action.triggered.connect(self._on_save_database)

        save_as_action = file_menu.addAction("Save &As…")
        save_as_action.triggered.connect(self._on_save_as_database)

        if self.current_user.is_admin:
            file_menu.addSeparator()

            import_export_menu = file_menu.addMenu("Import / &Export")

            backup_all_action = import_export_menu.addAction("&Back Up Everything…")
            backup_all_action.triggered.connect(self._on_backup_everything)

            restore_all_action = import_export_menu.addAction("Restore E&verything…")
            restore_all_action.triggered.connect(self._on_restore_everything)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        # Settings menu, adjacent to File.
        settings_menu = self.menuBar().addMenu("&Settings")

        bank_action = settings_menu.addAction("&Bank Account")
        bank_action.triggered.connect(self._on_bank_account_settings)

        # Users menu: managing accounts is for admins only; leaving a session
        # is for everyone. Both ways out are offered because they differ in
        # what a cancelled sign-in then does. Switch User keeps this session
        # alive behind the sign-in screen, so cancelling returns to it; Log
        # Out ends the session, so cancelling closes the application. Only
        # Switch User takes an ellipsis: it needs to be told WHO before it has
        # done anything, while Log Out is complete the moment it is chosen.
        users_menu = self.menuBar().addMenu("&Users")
        if self.current_user.is_admin:
            manage_action = users_menu.addAction("&Manage Users…")
            manage_action.triggered.connect(self._on_manage_users)
            users_menu.addSeparator()
        switch_action = users_menu.addAction("&Switch User…")
        switch_action.triggered.connect(self._on_switch_user)
        sign_out_action = users_menu.addAction("Log &Out")
        sign_out_action.triggered.connect(self._on_sign_out)

        # Help menu
        help_menu = self.menuBar().addMenu("&Help")
        about_action = help_menu.addAction("&About ClearBudget")
        check_updates_action = help_menu.addAction("Check for &Updates")
        how_it_works_action = help_menu.addAction("How It Works")
        licence_action = help_menu.addAction("View Licence (LGPL-3.0)")
        how_it_works_action.triggered.connect(self._on_how_it_works)
        about_action.triggered.connect(self._on_about)
        check_updates_action.triggered.connect(self._on_check_updates)
        licence_action.triggered.connect(self._on_licence)
