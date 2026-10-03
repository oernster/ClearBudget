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

# The columns sign-in reads from it (see auth.user_store). A `users` table of
# any other shape was measured passing a restore and then failing every
# sign-in with "no such column".
ACCOUNTS_REQUIRED_COLUMNS = frozenset(
    {"id", "username", "password_hash", "recovery_code_hash", "is_admin"}
)

# What SQLite's quick_check reports for a database whose pages all read.
_INTEGRITY_OK = "ok"

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


def _missing_columns(conn, table: str, required: frozenset[str] | set[str]) -> str:
    """The required columns ``table`` lacks, joined for a message; else ''."""
    present = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    return ", ".join(sorted(set(required) - present))


def _integrity_error(conn) -> str | None:
    """None when every page of the database reads; else what SQLite found.

    The schema checks read `sqlite_master` and nothing else, so a file whose
    data pages were damaged behind an intact schema passed them and then
    failed to open once it had replaced the user's budget. `quick_check`
    walks every page; it skips only the index-to-table cross-check, which
    costs far more and protects nothing a damaged page would not show.
    """
    # quick_check always answers with at least one row: "ok" or the first fault.
    verdict = conn.execute("PRAGMA quick_check").fetchone()[0]
    if verdict == _INTEGRITY_OK:
        return None
    return f"The file is damaged: {verdict}"


def validate_db(path: Path) -> str | None:
    """Return an error string if path is not a valid ClearBudget db, else None.

    Shape first, then every data page: a budget must have the tables and
    columns the app reads AND be readable all the way through.
    """
    import sqlite3

    conn = None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        missing_tables = set(REQUIRED_SCHEMA) - tables
        if missing_tables:
            missing = ", ".join(sorted(missing_tables))
            return f"Not a ClearBudget database - missing tables: {missing}"

        for table, required_cols in REQUIRED_SCHEMA.items():
            missing_cols = _missing_columns(conn, table, required_cols)
            if missing_cols:
                return (
                    f"Not a ClearBudget database - table '{table}' "
                    f"missing columns: {missing_cols}"
                )
        return _integrity_error(conn)
    except sqlite3.DatabaseError as exc:
        return f"Not a valid SQLite database: {exc}"
    finally:
        # A connect that failed leaves nothing to close.
        if conn is not None:
            conn.close()


def validate_accounts_db(path: Path) -> str | None:
    """None when ``path`` is an accounts database sign-in can use; else why not.

    The same two questions as `validate_db`, asked of the accounts store:
    the `users` table with every column sign-in reads, then every page.
    """
    import sqlite3

    conn = None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        found = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (_ACCOUNTS_TABLE,),
        ).fetchone()
        if found is None:
            return "The accounts database in the backup holds no users table."
        missing = _missing_columns(conn, _ACCOUNTS_TABLE, ACCOUNTS_REQUIRED_COLUMNS)
        if missing:
            return (
                "The accounts database in the backup is missing columns: " f"{missing}"
            )
        damage = _integrity_error(conn)
        if damage:
            return f"The accounts database in the backup: {damage}"
        return None
    except sqlite3.DatabaseError:
        return "The accounts database in the backup is not readable."
    finally:
        if conn is not None:
            conn.close()
