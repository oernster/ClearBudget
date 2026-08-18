"""Flow helper for the Bank Account Settings dialog - keeps main_window under LOC limit."""

from clear_budget.ui.widgets.bank_account_settings_dialog import (
    BankAccountSettingsDialog,
)


def run_bank_account_settings_flow(parent, budget_service) -> None:
    """Show the Bank Account Settings dialog and persist any changes."""
    dlg = BankAccountSettingsDialog(
        parent,
        overdraft_limit=budget_service.get_overdraft_limit(),
        overdraft_apr_basis_points=budget_service.get_overdraft_apr_basis_points(),
        safe_to_spend_floor=budget_service.get_safe_to_spend_floor(),
        sustainable_window_months=budget_service.get_sustainable_window_months(),
    )
    if dlg.exec() != BankAccountSettingsDialog.DialogCode.Accepted:
        return
    if dlg.overdraft_limit is not None:
        budget_service.set_overdraft_limit(amount=dlg.overdraft_limit)
    if dlg.overdraft_apr_basis_points is not None:
        budget_service.set_overdraft_apr_basis_points(
            basis_points=dlg.overdraft_apr_basis_points
        )
    if dlg.safe_to_spend_floor is not None:
        budget_service.set_safe_to_spend_floor(amount=dlg.safe_to_spend_floor)
    if dlg.sustainable_window_months is not None:
        budget_service.set_sustainable_window_months(
            months=dlg.sustainable_window_months
        )
