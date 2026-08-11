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


def get_bank_balance_date_iso(conn) -> str | None:  # pragma: no cover
    if conn is None:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", ("bank_balance_date",))
    row = cursor.fetchone()
    return str(row["value"]) if row else None


def set_bank_balance_pence(
    conn, pence: int, today: _date | None = None
) -> None:  # pragma: no cover
    stamp = today or _date.today()  # noqa: DTZ011 (naive local dates)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("bank_balance", str(pence)),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("bank_balance_day", str(stamp.day)),
    )
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("bank_balance_date", stamp.isoformat()),
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


def get_safe_to_spend_floor_pence(conn) -> int:  # pragma: no cover
    if conn is None:
        return 0
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", ("safe_to_spend_floor",))
    row = cursor.fetchone()
    return int(row["value"]) if row else 0


def set_safe_to_spend_floor_pence(conn, pence: int) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("safe_to_spend_floor", str(pence)),
    )
    conn.commit()


def get_safe_to_spend_horizon(conn) -> str | None:  # pragma: no cover
    if conn is None:
        return None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT value FROM settings WHERE key = ?", ("safe_to_spend_horizon",)
    )
    row = cursor.fetchone()
    return str(row["value"]) if row else None


def set_safe_to_spend_horizon(conn, horizon: str) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("safe_to_spend_horizon", horizon),
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
