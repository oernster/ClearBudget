"""Database schema validation for import - extracted from MainWindow (LOC limit).

Two questions, deliberately separate. `validate_db` asks whether a file is a
budget this application can open. `is_accounts_database` asks whether it is the
ACCOUNTS store, which is a different file with a different job and lives in the
same directory the Load dialog opens on. Both answer "no" to a budget load;
they are told apart because only one of them has something useful to say about
what the user actually picked.
"""

from pathlib import Path

# The accounts store holds who may sign in. It is not a budget and it is never
# loadable as one; it sits beside every budget in the data directory, so it is
# one careless click away in the Load dialog.
_ACCOUNTS_TABLE = "users"

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


def is_accounts_database(path: Path) -> bool:
    """Whether `path` is the accounts store rather than a budget.

    Answered from the file's SHAPE, never from its name: a copy, a backup or a
    renamed accounts store is the same file with the same contents and must be
    refused the same way. It holds the `users` table and none of the budget
    tables; a budget holds the budget tables and no `users` table, so the two
    can never both be true.

    False for anything that is not a readable SQLite file at all. That is not
    this function's question; `validate_db` says it better.
    """
    import sqlite3

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.DatabaseError:
        return False
    try:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()
    return _ACCOUNTS_TABLE in tables and not (tables & set(REQUIRED_SCHEMA))


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
            return f"Not a ClearBudget database - missing tables: {missing}"

        for table, required_cols in REQUIRED_SCHEMA.items():
            cursor.execute(f"PRAGMA table_info({table})")
            present_cols = {r["name"] for r in cursor.fetchall()}
            missing_cols = required_cols - present_cols
            if missing_cols:
                conn.close()
                return (
                    f"Not a ClearBudget database - table '{table}' "
                    f"missing columns: "
                    f"{', '.join(sorted(missing_cols))}"
                )

        conn.close()
    except sqlite3.DatabaseError as exc:
        return f"Not a valid SQLite database: {exc}"
    finally:
        # Falling through to here means the connection opened, because a
        # connect that failed returns from the except clause instead.
        if conn is not None:  # pragma: no branch
            conn.close()
    return None
