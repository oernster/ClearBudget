"""Flow helper for the Preferences (currency) dialog - keeps main_window under LOC limit."""

from clear_budget.ui.widgets.currency_dialog import CurrencyDialog


def run_preferences_flow(parent, conn) -> bool:
    """Show the currency preferences dialog. Returns True if currency changed."""
    from clear_budget.shared.currency import set_currency

    row = conn.execute("SELECT value FROM settings WHERE key = 'currency'").fetchone()
    current_code = row["value"] if row else "GBP"
    dlg = CurrencyDialog(current_code, parent=parent)
    if dlg.exec() != CurrencyDialog.DialogCode.Accepted:
        return False
    new_code = dlg.selected_code
    if new_code == current_code:
        return False
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('currency', ?)",
        (new_code,),
    )
    conn.commit()
    set_currency(new_code)
    return True
