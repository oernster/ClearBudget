"""The sign-in screen a session starts at, first run or later.

Extracted from the composition root, which had grown past the file-size limit
(tests/structural/test_loc_limits.py). It is UI: it decides which dialog the
user is shown and reports who they turned out to be. The composition root
decides what to DO with that answer, which is a separate question and stays
there.
"""

from __future__ import annotations

from clear_budget.auth.models import User
from clear_budget.auth.remembered_login import RememberedLogin
from clear_budget.auth.user_store import UserStore


def run_login_flow(
    user_store: UserStore, remembered_login: RememberedLogin
) -> User | None:
    """Show the first-run or the sign-in dialog.

    Returns the authenticated user; None when the user backed out without
    signing in. What that None MEANS is the caller's to decide: it is a
    cancelled switch when a session is already running and a refusal to start
    when one is not.
    """
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
