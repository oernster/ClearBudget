"""Database schema validation for import - extracted from MainWindow (LOC limit)."""

from pathlib import Path

REQUIRED_SCHEMA: dict[str, set[str]] = {
    "bills": {
        "amount_pence",
        "payment_method_id",
        "category",
        "bill_type",
        "active",
    },
    "income_sources": {"amount_pence", "is_reliable", "day_of_month", "active"},
    "credit_cards": {
        "credit_limit_pence",
        "current_balance_used_pence",
        "payment_due_day",
        "active",
    },
    "payment_methods": {"name", "type"},
    "settings": {"key", "value"},
    "bill_month_overrides": {"bill_id", "year", "month", "amount_pence"},
    "bill_month_skips": {"bill_id", "year", "month"},
    "income_month_extras": {
        "year",
        "month",
        "name",
        "amount_pence",
        "day_of_month",
        "is_reliable",
    },
    "income_month_overrides": {"income_id", "year", "month", "amount_pence"},
    "income_month_skips": {"income_id", "year", "month"},
    "bill_month_paid": {"bill_id", "year", "month"},
    "income_month_received": {"income_id", "year", "month"},
}


def validate_db(path: Path) -> str | None:
    """Return an error string if path is not a valid ClearBudget db, else None."""
    import sqlite3

    conn = None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r["name"] for r in cursor.fetchall()}

        missing_tables = set(REQUIRED_SCHEMA) - tables
        if missing_tables:
            conn.close()
            missing = ", ".join(sorted(missing_tables))
            return f"Not a Clear Budget database - missing tables: {missing}"

        for table, required_cols in REQUIRED_SCHEMA.items():
            cursor.execute(f"PRAGMA table_info({table})")
            present_cols = {r["name"] for r in cursor.fetchall()}
            missing_cols = required_cols - present_cols
            if missing_cols:
                conn.close()
                return (
                    f"Not a Clear Budget database - table '{table}' "
                    f"missing columns: "
                    f"{', '.join(sorted(missing_cols))}"
                )

        conn.close()
    except sqlite3.DatabaseError as exc:
        return f"Not a valid SQLite database: {exc}"
    finally:
        if conn is not None:
            conn.close()
    return None
