"""Settings-table read/write helpers for BudgetService - extracted for LOC limit."""

from datetime import date as _date


def get_bank_balance_pence(conn) -> int:  # pragma: no cover
    if conn is None:
        return 0
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", ("bank_balance",))
    row = cursor.fetchone()
    return int(row["value"]) if row else 0


def get_bank_balance_day(conn) -> int:  # pragma: no cover
    if conn is None:
        return 0
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", ("bank_balance_day",))
    row = cursor.fetchone()
    return int(row["value"]) if row else 0


DISCRETIONARY_BUFFER_DEFAULT_PERCENT = 20
DISCRETIONARY_BUFFER_MINIMUM_PENCE = 2000


def compute_discretionary_buffer_default(balance_pence: int) -> int:
    """Default discretionary buffer: 20% of balance, or £20, whichever is higher."""
    percent_pence = balance_pence * DISCRETIONARY_BUFFER_DEFAULT_PERCENT // 100
    return max(percent_pence, DISCRETIONARY_BUFFER_MINIMUM_PENCE)


def get_discretionary_buffer_pence(conn) -> int | None:  # pragma: no cover
    """Return the user-set discretionary buffer in pence, or None if unset."""
    if conn is None:
        return None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT value FROM settings WHERE key = ?", ("discretionary_buffer",)
    )
    row = cursor.fetchone()
    return int(row["value"]) if row else None


def set_discretionary_buffer_pence(conn, pence: int) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("discretionary_buffer", str(pence)),
    )
    conn.commit()


def set_bank_balance_pence(conn, pence: int) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("bank_balance", str(pence)),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("bank_balance_day", str(_date.today().day)),
    )
    conn.commit()
