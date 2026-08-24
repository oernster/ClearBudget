"""Account and session handlers for MainWindow.

Extracted from main_window.py as a mixin to keep that module under the 400-LOC
limit (enforced by tests/structural/test_loc_limits.py), alongside the menu and
navigation mixins. One concern: WHO this session belongs to, plus how
accounts on this machine are managed.

The two ways out of a session are deliberately different and the difference is
the reason both exist. Switching SUSPENDS: the window is hidden and its
database stays open, so cancelling the sign-in screen comes back to it.
Signing out ENDS: the composition root destroys the window and closes the
database, so there is nothing to come back to and cancelling the sign-in
screen closes the application. Neither loses anything, since the budget lives
on disk either way.
"""


class MainWindowAccountMixin:
    """Switching, signing out and managing the accounts on this machine."""

    def _on_switch_user(self) -> None:
        """Suspend this session and offer the sign-in screen.

        Hidden BEFORE the signal, never after: the composition root answers
        it by running a modal sign-in, so anything this method did afterwards
        would run against a window the root may already have replaced.
        """
        self.hide()
        self.switch_user_requested.emit()

    def _on_sign_out(self) -> None:
        """End this session outright, then return to the sign-in screen."""
        self.hide()
        self.sign_out_requested.emit()

    def _on_users(self) -> None:
        """The tray users button, which switches account.

        Switching is what the tray offers because the tray is a single click
        with no confirmation; it is also the only one of the two that is
        REVERSIBLE: cancel the sign-in and the session is still there. A
        one-click Log Out would end the session on a misclick, so Log Out
        stays on the menu where choosing it is deliberate.
        """
        self._on_switch_user()

    def _on_manage_users(self) -> None:
        """Open the admin screen listing every account on this machine."""
        from clear_budget.ui.widgets.user_management_dialog import UserManagementDialog

        dlg = UserManagementDialog(self.user_store, self.current_user, parent=self)
        dlg.exec()
