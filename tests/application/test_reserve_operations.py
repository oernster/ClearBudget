"""The reserves adapter: what the page asks the service for.

Read through the real repository against real SQLite rather than a fake,
because the figures the page prints are the ones the accrual produced and a
stand-in would only prove the adapter talks to itself.
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
TODAY = date(2026, 8, 25)
FULL_PENCE = 62000


def _service(conn, *, with_reserves: bool = True) -> BudgetService:
    bills = SQLiteBillRepository(conn)
    income = SQLiteIncomeSourceRepository(conn)
    methods = SQLitePaymentMethodRepository(conn)
    return BudgetService(
        bill_repo=bills,
        income_repo=income,
        payment_method_repo=methods,
        month_generator=MonthGenerator(bills, income),
        commitment_repo=SQLiteCommitmentRepository(conn) if with_reserves else None,
    )


@pytest.fixture
def conn(tmp_path):
    connection = sqlite3.connect(tmp_path / "budget.db")
    connection.row_factory = sqlite3.Row
    create_schema(connection)
    yield connection
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


class TestWithoutAStore:
    def test_a_budget_with_no_reserves_store_lists_nothing(self, conn):
        """Every existing construction site keeps working, reserving nothing."""
        assert _service(conn, with_reserves=False).list_commitments() == []

    def test_its_floor_is_flat(self, conn):
        assert _service(conn, with_reserves=False).get_reserve_floor().is_flat


class TestReadsAndWrites:
    def test_a_commitment_can_be_added_and_listed(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        assert [c.name for c in service.list_commitments()] == ["Car insurance"]

    def test_an_update_is_stored(self, conn):
        service = _service(conn)
        stored = service.add_commitment(commitment=_commitment())
        service.update_commitment(
            commitment=_commitment(id=stored.id, name="MOT", amount=Amount(pence=5400))
        )
        assert service.list_commitments()[0].name == "MOT"

    def test_ending_keeps_the_months_it_ran_in(self, conn):
        service = _service(conn)
        stored = service.add_commitment(commitment=_commitment())
        service.end_commitment(commitment_id=stored.id, final_month=AUGUST)
        assert service.list_commitments()[0].final_month == AUGUST

    def test_deleting_removes_it(self, conn):
        service = _service(conn)
        stored = service.add_commitment(commitment=_commitment())
        service.delete_commitment(commitment_id=stored.id)
        assert service.list_commitments() == []

    def test_an_inactive_commitment_can_be_asked_for(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment(active=False))
        assert service.list_commitments() == []
        assert len(service.list_commitments(include_inactive=True)) == 1


class TestTheRowsThePageDraws:
    def test_an_empty_budget_has_no_rows(self, conn):
        assert _service(conn).get_reserve_rows(today=TODAY) == []

    def test_a_row_carries_the_figures_the_table_prints(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        row = service.get_reserve_rows(today=TODAY)[0]
        assert row.monthly_pence == 20667
        assert row.natural_pence == 5167
        assert row.held_pence + row.outstanding_pence == FULL_PENCE

    def test_a_short_first_cycle_is_marked_steep(self, conn):
        """The page explains a steep figure rather than just printing it."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        assert service.get_reserve_rows(today=TODAY)[0].is_steep

    def test_a_full_cycle_ahead_is_not_steep(self, conn):
        service = _service(conn)
        service.add_commitment(
            commitment=_commitment(due_date=date(2027, 8, 14), created_month=AUGUST)
        )
        assert not service.get_reserve_rows(today=TODAY)[0].is_steep

    def test_rows_default_to_today(self, conn):
        """The page calls it with no date, so that path is exercised too."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        assert len(service.get_reserve_rows()) == 1


class TestWhatIsHeldBack:
    def test_nothing_is_held_back_by_an_empty_budget(self, conn):
        assert _service(conn).get_reserved_today_pence(today=TODAY) == 0

    def test_a_commitment_holds_back_part_of_its_amount(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        held = service.get_reserved_today_pence(today=TODAY)
        assert 0 < held < FULL_PENCE

    def test_it_defaults_to_today(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        assert service.get_reserved_today_pence() >= 0


class TestTheFloor:
    def test_it_carries_the_buffer_when_one_is_set(self, conn):
        service = _service(conn)
        service.set_recommendation_buffer(enabled=True, amount=Amount(pence=15000))
        assert service.get_reserve_floor().buffer_pence == 15000

    def test_a_disabled_buffer_holds_nothing(self, conn):
        service = _service(conn)
        service.set_recommendation_buffer(enabled=False, amount=Amount(pence=15000))
        assert service.get_reserve_floor().buffer_pence == 0

    def test_it_carries_the_commitments(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        assert len(service.get_reserve_floor().commitments) == 1

    def test_everyday_spending_starts_unset(self, conn):
        assert _service(conn).get_variable_spend() is None

    def test_a_stored_everyday_figure_is_read_back(self, conn):
        from clear_budget.application.services._settings_operations import (
            set_variable_spend_monthly_pence,
        )

        set_variable_spend_monthly_pence(conn, 30000)
        service = _service(conn)
        assert service.get_variable_spend() == Amount(pence=30000)
        assert service.get_reserve_floor().variable_spend_monthly_pence == 30000
