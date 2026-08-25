"""The commitments store, against real SQLite rather than a stand-in.

A commitment is read back through the same conversion the application uses,
so a column that stops round-tripping fails here rather than in a projection
three layers up.
"""

import shutil
import sqlite3
from dataclasses import replace
from datetime import date

import pytest

from clear_budget.domain.entities.commitment import Commitment
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.recurrence import Recurrence
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite._schema import create_schema
from clear_budget.infrastructure.sqlite.commitment_repository import (
    SQLiteCommitmentRepository,
)

AUGUST = YearMonth(year=2026, month=8)
FULL_PENCE = 62000


@pytest.fixture
def repo(tmp_path):
    connection = sqlite3.connect(tmp_path / "budget.db")
    connection.row_factory = sqlite3.Row
    create_schema(connection)
    yield SQLiteCommitmentRepository(conn=connection)
    connection.close()


def _commitment(**overrides) -> Commitment:
    fields = {
        "id": 0,
        "name": "Car insurance",
        "amount": Amount(pence=FULL_PENCE),
        "due_date": date(2026, 11, 14),
        "recurrence": Recurrence.annual(),
        "created_month": AUGUST,
    }
    fields.update(overrides)
    return Commitment(**fields)


class TestRoundTrip:
    def test_a_stored_commitment_reads_back_unchanged(self, repo):
        stored = repo.add(commitment=_commitment())
        assert repo.get_by_id(commitment_id=stored.id) == stored

    def test_adding_assigns_an_id(self, repo):
        assert repo.add(commitment=_commitment()).id > 0

    def test_an_absent_commitment_is_none(self, repo):
        assert repo.get_by_id(commitment_id=404) is None

    def test_every_optional_field_survives(self, repo):
        stored = repo.add(
            commitment=_commitment(
                already_held=Amount(pence=3000),
                category="housing",
                final_month=YearMonth(year=2027, month=1),
            )
        )
        back = repo.get_by_id(commitment_id=stored.id)
        assert back.already_held == Amount(pence=3000)
        assert back.category == "housing"
        assert back.final_month == YearMonth(year=2027, month=1)

    @pytest.mark.parametrize(
        "recurrence",
        [Recurrence.once(), Recurrence.annual(), Recurrence.every_months(3)],
    )
    def test_every_recurrence_survives(self, repo, recurrence):
        stored = repo.add(commitment=_commitment(recurrence=recurrence))
        assert repo.get_by_id(commitment_id=stored.id).recurrence == recurrence


class TestListing:
    def test_an_empty_store_lists_nothing(self, repo):
        assert repo.list_all() == []

    def test_they_are_ordered_by_the_day_they_fall_due(self, repo):
        repo.add(commitment=_commitment(name="Later", due_date=date(2026, 12, 20)))
        repo.add(commitment=_commitment(name="Sooner", due_date=date(2026, 10, 2)))
        assert [c.name for c in repo.list_all()] == ["Sooner", "Later"]

    def test_an_inactive_commitment_is_left_out_by_default(self, repo):
        repo.add(commitment=_commitment(active=False))
        assert repo.list_all() == []

    def test_an_inactive_commitment_can_be_asked_for(self, repo):
        repo.add(commitment=_commitment(active=False))
        assert len(repo.list_all(include_inactive=True)) == 1


class TestTheMonthWindow:
    def test_a_commitment_applies_from_the_month_it_was_entered(self, repo):
        repo.add(commitment=_commitment())
        assert repo.list_for_month(year_month=AUGUST)

    def test_it_does_not_apply_before_then(self, repo):
        repo.add(commitment=_commitment())
        assert repo.list_for_month(year_month=YearMonth(year=2026, month=7)) == []

    def test_it_does_not_apply_after_its_final_month(self, repo):
        repo.add(commitment=_commitment(final_month=YearMonth(year=2026, month=9)))
        assert repo.list_for_month(year_month=YearMonth(year=2026, month=10)) == []


class TestChanging:
    def test_an_update_is_stored(self, repo):
        stored = repo.add(commitment=_commitment())
        repo.update(commitment=replace(stored, name="MOT"))
        assert repo.get_by_id(commitment_id=stored.id).name == "MOT"

    def test_ending_keeps_the_months_it_ran_in(self, repo):
        """The rule bills and income already follow."""
        stored = repo.add(commitment=_commitment())
        repo.end_from(commitment_id=stored.id, final_month=YearMonth(2026, 9))
        assert repo.list_for_month(year_month=AUGUST)
        assert repo.list_for_month(year_month=YearMonth(year=2026, month=10)) == []

    def test_deleting_removes_it_outright(self, repo):
        stored = repo.add(commitment=_commitment())
        repo.delete(commitment_id=stored.id)
        assert repo.get_by_id(commitment_id=stored.id) is None


class TestItTravelsWithTheBudget:
    def test_a_commitment_survives_the_file_being_copied(self, repo, tmp_path):
        """Save, Load and the full backup all copy the database file."""
        stored = repo.add(commitment=_commitment())
        repo.conn.close()
        copy_path = tmp_path / "copy.db"
        shutil.copy(tmp_path / "budget.db", copy_path)
        connection = sqlite3.connect(copy_path)
        connection.row_factory = sqlite3.Row
        copied = SQLiteCommitmentRepository(conn=connection)
        assert copied.get_by_id(commitment_id=stored.id) == stored
        connection.close()
