"""The budget database a session opens, plus the currency it opens under.

These moved out of the composition root when it outgrew the file-size limit,
which put them inside the coverage gate for the first time. They were never
covered while they lived in main.py, so this is new ground rather than a
port: everything asserted here was previously only exercised by running the
application.
"""

from __future__ import annotations

import pytest

from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.session_database import (
    load_currency,
    open_user_database,
)
from clear_budget.shared import currency as currency_module
from clear_budget.shared.budget_registry import active_db_path
from clear_budget.shared.db_ownership import challenge_required, owner_from_stamp


@pytest.fixture(autouse=True)
def restore_active_currency():
    """Put the process-wide active currency back after each test.

    `set_currency` writes a module global, so a test that changes it would
    otherwise decide what every later test formats its amounts in.
    """
    before = currency_module.get_currency()
    yield
    currency_module.set_currency(before.code)


def test_opening_a_users_database_creates_it_with_a_schema() -> None:
    """A first sign-in has no file yet, so opening must make a usable one."""
    database = open_user_database("ada")
    try:
        assert database.conn is not None
        assert database.db_path == active_db_path("ada")
        assert database.db_path.exists()
        # The schema is what makes it usable rather than merely present.
        tables = {
            row["name"]
            for row in database.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "settings" in tables
    finally:
        database.close()


def test_opening_twice_returns_the_same_budget_file() -> None:
    """The registry decides the path, so it cannot drift between sessions."""
    first = open_user_database("grace")
    first.close()
    second = open_user_database("grace")
    try:
        assert second.db_path == first.db_path
    finally:
        second.close()


def test_a_saved_currency_is_activated() -> None:
    """The budget's own setting wins, which is the whole point of storing it."""
    database = open_user_database("ada")
    try:
        database.conn.execute(
            "INSERT INTO settings (key, value) VALUES ('currency', 'USD')"
        )
        database.conn.commit()
        load_currency(database)
        assert currency_module.get_currency().code == "USD"
    finally:
        database.close()


def test_a_budget_that_never_named_a_currency_falls_back_to_sterling() -> None:
    """No row is not an error: it is a budget that never chose."""
    currency_module.set_currency("USD")
    database = open_user_database("grace")
    try:
        load_currency(database)
        assert currency_module.get_currency().code == "GBP"
    finally:
        database.close()


def test_a_closed_database_activates_nothing(tmp_path) -> None:
    """Teardown calls this with no connection; it must not raise there."""
    currency_module.set_currency("USD")
    load_currency(Database(tmp_path / "never-opened.db"))
    assert currency_module.get_currency().code == "USD"


def test_opening_a_budget_stamps_who_it_belongs_to() -> None:
    """Ownership travels with the file, so copying it cannot launder it."""
    database = open_user_database("grace")
    try:
        assert owner_from_stamp(database.db_path) == "grace"
    finally:
        database.close()


def test_the_stamp_survives_being_reopened_by_someone_else() -> None:
    """A second open must not re-stamp: opening a file is not claiming it."""
    database = open_user_database("grace")
    path = database.db_path
    database.close()
    reopened = open_user_database("grace")
    reopened.close()
    assert owner_from_stamp(path) == "grace"
    assert challenge_required(path, "mallory", ["grace", "mallory"]) == "grace"
