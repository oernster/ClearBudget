"""Flow helper for the Bank Account Settings dialog.

Split out to keep main_window under the module size limit.
"""

from clear_budget.ui.widgets.bank_account_settings_dialog import (
    BankAccountSettingsDialog,
)


def _current_currency_code(conn) -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = 'currency'").fetchone()
    return row["value"] if row else "GBP"


def run_bank_account_settings_flow(parent, budget_service) -> bool:
    """Show the Bank Account Settings dialog and persist any changes.

    Returns True when the DISPLAY CURRENCY changed, because that one setting
    relabels every figure in the window: the caller rebuilds the session
    (`database_replaced`) exactly as the old Preferences dialog did. Every
    other change is picked up by an ordinary month refresh.
    """
    conn = budget_service.bill_repo.conn
    current_code = _current_currency_code(conn)
    dlg = BankAccountSettingsDialog(
        parent,
        overdraft_limit=budget_service.get_overdraft_limit(),
        overdraft_apr_basis_points=budget_service.get_overdraft_apr_basis_points(),
        safe_to_spend_floor=budget_service.get_safe_to_spend_floor(),
        sustainable_window_months=budget_service.get_sustainable_window_months(),
        currency_code=current_code,
    )
    if dlg.exec() != BankAccountSettingsDialog.DialogCode.Accepted:
        return False
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
    new_code = dlg.currency_code
    if new_code == current_code:
        return False
    from clear_budget.shared.currency import set_currency

    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('currency', ?)",
        (new_code,),
    )
    conn.commit()
    set_currency(new_code)
    return True
