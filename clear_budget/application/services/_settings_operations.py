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


def get_safe_to_spend_floor_pence(conn) -> int | None:  # pragma: no cover
    """Stored floor pence; None when never set (the caller applies the
    default buffer; an explicitly saved zero is honoured as zero)."""
    if conn is None:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", ("safe_to_spend_floor",))
    row = cursor.fetchone()
    return int(row["value"]) if row else None


def set_safe_to_spend_floor_pence(conn, pence: int) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("safe_to_spend_floor", str(pence)),
    )
    conn.commit()


def get_sustainable_window_months(conn) -> int | None:  # pragma: no cover
    if conn is None:
        return None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT value FROM settings WHERE key = ?", ("sustainable_window_months",)
    )
    row = cursor.fetchone()
    return int(row["value"]) if row else None


def set_sustainable_window_months(conn, months: int) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("sustainable_window_months", str(months)),
    )
    conn.commit()


def get_recommendation_buffer_pence(conn) -> int | None:  # pragma: no cover
    """Stored emergency buffer for the Recommendations page; None = never set."""
    if conn is None:
        return None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT value FROM settings WHERE key = ?", ("recommendation_buffer",)
    )
    row = cursor.fetchone()
    return int(row["value"]) if row else None


def set_recommendation_buffer_pence(conn, pence: int) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("recommendation_buffer", str(pence)),
    )
    conn.commit()


def get_recommendation_buffer_enabled(conn) -> bool:  # pragma: no cover
    if conn is None:
        return False
    cursor = conn.cursor()
    cursor.execute(
        "SELECT value FROM settings WHERE key = ?", ("recommendation_buffer_enabled",)
    )
    row = cursor.fetchone()
    return bool(int(row["value"])) if row else False


def set_recommendation_buffer_enabled(conn, enabled: bool) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("recommendation_buffer_enabled", "1" if enabled else "0"),
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


def get_variable_spend_monthly_pence(conn) -> int | None:  # pragma: no cover
    """Expected everyday spending a month; None = never set.

    None and zero are different answers and are kept apart. Zero is a claim
    that nothing leaves the account outside the entered bills; None is the
    absence of a claim, which the page reports in words rather than treating
    as a figure.
    """
    if conn is None:
        return None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT value FROM settings WHERE key = ?", ("variable_spend_monthly",)
    )
    row = cursor.fetchone()
    return int(row["value"]) if row else None


def set_variable_spend_monthly_pence(conn, pence: int) -> None:  # pragma: no cover
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ("variable_spend_monthly", str(pence)),
    )
    conn.commit()
