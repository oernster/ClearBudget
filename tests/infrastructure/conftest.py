"""Fixtures for infrastructure tests."""

import pytest

from clear_budget.infrastructure.sqlite.database import Database


@pytest.fixture
def db(tmp_path):
    """Create an in-memory SQLite database for testing."""
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    database.connect()
    database.create_schema()

    yield database

    database.close()
