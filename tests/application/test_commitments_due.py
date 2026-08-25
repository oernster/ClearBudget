"""Tests for the commitments the Monthly Budget shows as already covered.

Split from `test_reserve_operations` so that file stays inside the line
limit; one file, one question, which here is "what actually leaves during
this month".
"""

import sqlite3
from datetime import date

import pytest

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.commitment import Commitment
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.recurrence import Recurrence
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite._schema import create_schema
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.commitment_repository import (
    SQLiteCommitmentRepository,
)
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)

AUGUST = YearMonth(year=2026, month=8)
NOVEMBER = YearMonth(year=2026, month=11)
FULL_PENCE = 62000


@pytest.fixture
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "budget.db")
    connection.row_factory = sqlite3.Row
    create_schema(connection)
    yield connection
    connection.close()


def _service(conn) -> BudgetService:
    bills = SQLiteBillRepository(conn)
    income = SQLiteIncomeSourceRepository(conn)
    methods = SQLitePaymentMethodRepository(conn)
    return BudgetService(
        bill_repo=bills,
        income_repo=income,
        payment_method_repo=methods,
        month_generator=MonthGenerator(bills, income),
        commitment_repo=SQLiteCommitmentRepository(conn),
    )


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


class TestWhatLeavesThisMonth:
    """The reminder the Monthly Budget shows, so nothing is entered twice.

    A commitment due this month is money that really does leave the account;
    it is already held back day by day. The page shows it and counts it
    nowhere, which is why the question "is it due HERE" has to be exact.
    """

    def test_a_month_with_no_commitments_has_nothing_due(self, conn):
        assert _service(conn).get_commitments_due_in(year_month=AUGUST) == []

    def test_a_commitment_due_later_is_not_shown_yet(self, conn):
        """August is still saving for it; November is where it goes."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        assert service.get_commitments_due_in(year_month=AUGUST) == []

    def test_the_due_month_shows_it(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        due = service.get_commitments_due_in(year_month=NOVEMBER)
        assert [(row.name, row.day) for row in due] == [("Car insurance", 14)]

    def test_it_carries_what_actually_leaves(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        due = service.get_commitments_due_in(year_month=NOVEMBER)
        assert due[0].amount == Amount(pence=FULL_PENCE)

    def test_a_commitment_due_on_the_first_is_not_missed(self, conn):
        """The day a cycle closes belongs to that cycle, not the next one."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment(due_date=date(2026, 11, 1)))
        due = service.get_commitments_due_in(year_month=NOVEMBER)
        assert [row.day for row in due] == [1]

    def test_a_repeat_answers_for_the_cycle_the_month_sits_in(self, conn):
        """Read from the live occurrence, never from the stored due date."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        next_year = YearMonth(year=2027, month=11)
        assert len(service.get_commitments_due_in(year_month=next_year)) == 1

    def test_an_ended_commitment_is_gone_from_the_table(self, conn):
        service = _service(conn)
        stored = service.add_commitment(commitment=_commitment())
        service.end_commitment(
            commitment_id=stored.id, final_month=YearMonth(year=2026, month=9)
        )
        assert service.get_commitments_due_in(year_month=NOVEMBER) == []

    def test_two_due_the_same_month_are_ordered_by_day(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        service.add_commitment(
            commitment=_commitment(name="MOT", due_date=date(2026, 11, 3))
        )
        due = service.get_commitments_due_in(year_month=NOVEMBER)
        assert [row.day for row in due] == [3, 14]
