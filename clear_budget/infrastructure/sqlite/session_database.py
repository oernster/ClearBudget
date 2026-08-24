"""Opening the budget database a signed-in session runs on.

Extracted from the composition root, which had grown past the file-size limit
(tests/structural/test_loc_limits.py). It is a cohesive concern in its own
right: everything here answers one question, WHICH file this session opens and
what state it is opened in. The composition root keeps the wiring that follows.
"""

from __future__ import annotations

from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.shared.config import Config
from clear_budget.shared.currency import set_currency

# The currency a budget falls back to when its settings have never named one.
_DEFAULT_CURRENCY = "GBP"

_CURRENCY_QUERY = "SELECT value FROM settings WHERE key = 'currency'"


def open_user_database(username: str) -> Database:
    """Open (or create) the ACTIVE budget database for `username`.

    Which budget that is comes from the user's registry, which synthesises the
    legacy single budget when it has never been written. Switching budget is
    therefore a registry write plus the existing `database_replaced` reload,
    with no new session plumbing: this one function is the only place that
    decides which file a session opens.
    """
    from clear_budget.shared.budget_registry import active_db_path

    config = Config.for_user(username)
    config.ensure_directories()
    database = Database(active_db_path(username))
    database.connect()
    database.create_schema()
    return database


def load_currency(database: Database) -> None:
    """Activate the currency saved in this budget's settings.

    A database that is not open activates nothing rather than raising: the
    caller is mid-session-teardown in that case and there is no budget whose
    currency could be meant.
    """
    if database.conn is None:
        return
    row = database.conn.execute(_CURRENCY_QUERY).fetchone()
    set_currency(row["value"] if row else _DEFAULT_CURRENCY)
