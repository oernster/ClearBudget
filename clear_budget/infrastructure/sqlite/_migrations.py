"""Numbered schema migrations, applied in order and failing loudly.

The previous mechanism was a sequence of `ALTER TABLE ... ADD COLUMN` statements
each wrapped in `except Exception: pass`, on the assumption that a failure meant
the column was already present. That assumption is unverifiable: a corrupt file,
a locked database and a full disk all raise as well, and each one became a silent
no-op with the application continuing against a schema it had never checked.

Two changes remove that. A column is added only after reading `PRAGMA table_info`,
so "already present" is established by looking rather than inferred from an
exception, and every other failure propagates. A `schema_version` row then records
how far the database has been taken, so each migration runs once, in order, rather
than being re-attempted on every startup.

Both a new database and one predating this module converge on the same state: the
baseline DDL creates current tables in full, so every column step finds its column
already there and does nothing, and the version is recorded at the end.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

# The single row holding the version. Structural, not a domain value.
_VERSION_ROW_ID = 1
_BASELINE_VERSION = 0

Migration = Callable[[sqlite3.Cursor], None]


def _ensure_version_table(cursor: sqlite3.Cursor) -> None:
    """Create the version table and seed it at the baseline if it is new."""
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        " id INTEGER PRIMARY KEY CHECK (id = 1),"
        " version INTEGER NOT NULL"
        ")"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO schema_version (id, version) VALUES (?, ?)",
        (_VERSION_ROW_ID, _BASELINE_VERSION),
    )


def read_version(cursor: sqlite3.Cursor) -> int:
    """Return the version this database has been migrated to."""
    cursor.execute(
        "SELECT version FROM schema_version WHERE id = ?", (_VERSION_ROW_ID,)
    )
    row = cursor.fetchone()
    return _BASELINE_VERSION if row is None else int(row[0])


def _write_version(cursor: sqlite3.Cursor, version: int) -> None:
    cursor.execute(
        "UPDATE schema_version SET version = ? WHERE id = ?",
        (version, _VERSION_ROW_ID),
    )


def _column_names(cursor: sqlite3.Cursor, table: str) -> frozenset[str]:
    """Return the column names of a table, empty if the table does not exist."""
    cursor.execute(f"PRAGMA table_info({table})")
    name_index = 1
    return frozenset(str(row[name_index]) for row in cursor.fetchall())


def _add_column(
    cursor: sqlite3.Cursor, table: str, column: str, definition: str
) -> None:
    """Add a column unless it is already present.

    Presence is read from the table rather than inferred from a failure, so any
    error raised here is a real one and is allowed to propagate.
    """
    if column in _column_names(cursor, table):
        return
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _add_columns(
    cursor: sqlite3.Cursor, table: str, columns: tuple[tuple[str, str], ...]
) -> None:
    for column, definition in columns:
        _add_column(cursor, table, column, definition)


def _m01_credit_card_detail_columns(cursor: sqlite3.Cursor) -> None:
    """Interest, expiry, minimum payment and the active flag on a card."""
    _add_columns(
        cursor,
        "credit_cards",
        (
            ("interest_rate_apr", "REAL DEFAULT NULL"),
            ("payment_due_day", "INTEGER DEFAULT 1"),
            ("card_expiry_month", "INTEGER DEFAULT NULL"),
            ("card_expiry_year", "INTEGER DEFAULT NULL"),
            ("minimum_payment_pence", "INTEGER DEFAULT NULL"),
            ("active", "INTEGER DEFAULT 1"),
        ),
    )


def _m02_bill_target_card(cursor: sqlite3.Cursor) -> None:
    """Link a credit_payment bill to the card it pays off."""
    _add_column(cursor, "bills", "target_card_id", "INTEGER DEFAULT NULL")


def _m03_bill_override_day(cursor: sqlite3.Cursor) -> None:
    """Allow a month override to move the day as well as the amount."""
    _add_column(cursor, "bill_month_overrides", "day_of_month", "INTEGER DEFAULT NULL")


def _m04_card_minimum_payment_percent(cursor: sqlite3.Cursor) -> None:
    """Per-card minimum payment expressed as a percentage."""
    _add_column(cursor, "credit_cards", "minimum_payment_percent", "REAL DEFAULT NULL")


def _m05_card_balance_applied_anchor(cursor: sqlite3.Cursor) -> None:
    """Track the month, and day within it, a balance was last folded in."""
    _add_columns(
        cursor,
        "credit_cards",
        (
            ("balance_applied_year", "INTEGER DEFAULT NULL"),
            ("balance_applied_month", "INTEGER DEFAULT NULL"),
            ("balance_applied_day", "INTEGER DEFAULT NULL"),
        ),
    )


def _m06_income_extra_received(cursor: sqlite3.Cursor) -> None:
    """Received flag on one-off income rows."""
    _add_column(cursor, "income_month_extras", "received", "INTEGER NOT NULL DEFAULT 0")


def _m07_retire_one_time_category(cursor: sqlite3.Cursor) -> None:
    """Fold the retired one_time category into discretionary.

    "This month only" on Add covers the one-off case now. Archived month
    snapshots keep their historical label and are not touched.
    """
    cursor.execute(
        "UPDATE bills SET category = 'discretionary' WHERE category = 'one_time'"
    )


def _m08_bill_amount_changes(cursor: sqlite3.Cursor) -> None:
    """A bill's amount changing from a month onward (the rent increase).

    One row per change rather than an edit in place, so an earlier month keeps
    the amount it actually had.
    """
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS bill_amount_changes ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " bill_id INTEGER NOT NULL,"
        " effective_year INTEGER NOT NULL,"
        " effective_month INTEGER NOT NULL,"
        " amount_pence INTEGER NOT NULL,"
        " UNIQUE(bill_id, effective_year, effective_month),"
        " FOREIGN KEY (bill_id) REFERENCES bills(id)"
        ")"
    )


_MIGRATIONS: tuple[Migration, ...] = (
    _m01_credit_card_detail_columns,
    _m02_bill_target_card,
    _m03_bill_override_day,
    _m04_card_minimum_payment_percent,
    _m05_card_balance_applied_anchor,
    _m06_income_extra_received,
    _m07_retire_one_time_category,
    _m08_bill_amount_changes,
)

# Derived from the list so the two cannot drift apart.
LATEST_VERSION = len(_MIGRATIONS)


def apply_pending(cursor: sqlite3.Cursor) -> int:
    """Apply every migration the database has not yet had, in order.

    Returns the version the database now sits at.
    """
    _ensure_version_table(cursor)
    current = read_version(cursor)
    first_migration_number = 1
    for number, migration in enumerate(_MIGRATIONS, start=first_migration_number):
        if number <= current:
            continue
        migration(cursor)
        _write_version(cursor, number)
    return read_version(cursor)
