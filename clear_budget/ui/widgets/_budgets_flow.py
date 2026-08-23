"""Budget flows: create a new budget or open the budget manager.

Two entry points, because the two surfaces answer different questions.
File | New Budget asks one thing and does it. The tray's switch button opens
the manager, where the whole set is visible.

Both return True when the ACTIVE budget changed, which is the caller's cue to
emit `database_replaced` and let main rebuild the session on the new file.

Extracted from MainWindow so the window module stays under the LOC limit and
each flow is one readable recipe, exactly as the save/load flows are.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from clear_budget.shared.budget_registry import BudgetRegistryError, create_budget
from clear_budget.ui.widgets.budgets_dialog import BudgetsDialog, prompt_budget_name

_NEW_BUDGET_PROMPT = (
    "Name for the new budget:\n\n"
    "It starts empty. Your current budget is left exactly as it is; you "
    "can switch back to it at any time."
)


def run_new_budget_flow(parent, username: str) -> bool:
    """Create a named empty budget and make it active. True when one was made.

    There is no confirmation and nothing to warn about: this creates, it never
    destroys. The double-confirm wipe this replaced existed only because a user
    had exactly one budget, so the sole way to hand them an empty one was to
    empty the one they had.
    """
    name = prompt_budget_name(parent, "New Budget", _NEW_BUDGET_PROMPT)
    if name is None:
        return False
    try:
        create_budget(username, name)
    except BudgetRegistryError as exc:
        QMessageBox.warning(parent, "New Budget", str(exc))
        return False
    return True


def run_budgets_flow(parent, username: str) -> bool:
    """Open the budget manager. True when the active budget changed."""
    dialog = BudgetsDialog(username, parent=parent)
    dialog.exec()
    return dialog.active_changed
