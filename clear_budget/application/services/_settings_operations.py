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


def get_overdraft_limit_pence(conn) -> int:  # pragma: no cover
    if conn is None:
        return 0
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", ("overdraft_limit",))
    row = cursor.fetchone()
    return int(row["value"]) if row else 0


def set_overdraft_limit_pence(conn, pence: int) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("overdraft_limit", str(pence)),
    )
    conn.commit()


def get_overdraft_apr_basis_points(conn) -> int:  # pragma: no cover
    if conn is None:
        return 0
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", ("overdraft_apr_bp",))
    row = cursor.fetchone()
    return int(row["value"]) if row else 0


def set_overdraft_apr_basis_points(conn, basis_points: int) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("overdraft_apr_bp", str(basis_points)),
    )
    conn.commit()
