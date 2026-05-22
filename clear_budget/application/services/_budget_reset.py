"""Budget reset helper - wipes all user data from the active database."""

import sqlite3

_WIPE_TABLES = [
    "bill_month_skips",
    "bill_month_overrides",
    "month_bills",
    "month_income",
    "months",
    "bills",
    "income_sources",
    "credit_cards",
    "settings",
]

_BANK_ACCOUNT_INSERT = (
    "INSERT OR IGNORE INTO payment_methods (id, name, type)"
    " VALUES (1, 'Bank Account', 'bank')"
)


def reset_budget_data(conn: sqlite3.Connection) -> None:
    """Wipe all user data, preserving the Bank Account payment method (id=1)."""
    cursor = conn.cursor()
    for table in _WIPE_TABLES:
        cursor.execute(f"DELETE FROM {table}")
    cursor.execute("DELETE FROM payment_methods WHERE id != 1")
    cursor.execute(_BANK_ACCOUNT_INSERT)
    conn.commit()
