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
from clear_budget.domain.services.reserve_accrual import monthly_rate_pence
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


class TestWhatItCostsTheHeadline:
    """The line that connects this page to the figure the user looks at."""

    def _funded(self, conn):
        from clear_budget.application.services._settings_operations import (
            set_bank_balance_pence,
        )

        set_bank_balance_pence(conn, 300000, TODAY)
        return _service(conn)

    def test_nothing_set_aside_costs_nothing(self, conn):
        assert self._funded(conn).get_reserve_cost_pence(today=TODAY) == 0

    def test_a_commitment_lowers_the_headline_by_what_it_holds(self, conn):
        service = self._funded(conn)
        before = service.get_safe_to_spend(today=TODAY).amount_pence
        service.add_commitment(commitment=_commitment())
        after = service.get_safe_to_spend(today=TODAY)
        cost = service.get_reserve_cost_pence(today=TODAY)
        assert cost == before - after.amount_pence
        assert cost > 0

    def test_the_reserve_shows_in_the_result_beside_the_buffer(self, conn):
        service = self._funded(conn)
        service.add_commitment(commitment=_commitment())
        result = service.get_safe_to_spend(today=TODAY)
        assert result.reserved_pence > 0
        assert result.floor_pence > result.reserved_pence

    def test_the_bare_reading_ignores_every_commitment(self, conn):
        service = self._funded(conn)
        service.add_commitment(commitment=_commitment())
        assert (
            service.get_safe_to_spend_without_reserves(today=TODAY).reserved_pence == 0
        )

    def test_both_readings_default_to_today(self, conn):
        service = self._funded(conn)
        assert service.get_safe_to_spend_without_reserves() is not None
        assert service.get_reserve_cost_pence() >= 0


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


class TestTheFloorTheGraphPlots:
    """The per-day floor the month graph and its exports read the bars against.

    Built on the Safe to Spend buffer rather than the Reserves page's own,
    because the graph plots the bank balance and Safe to Spend already quotes
    a threshold against exactly that.
    """

    def test_it_gives_one_value_for_every_day_of_the_month(self, conn):
        values = _service(conn).get_bank_graph_floor_values(year_month=AUGUST)
        assert len(values) == 31

    def test_a_short_month_gets_its_own_length(self, conn):
        february = YearMonth(year=2026, month=2)
        values = _service(conn).get_bank_graph_floor_values(year_month=february)
        assert len(values) == 28

    def test_it_stands_on_the_safe_to_spend_buffer(self, conn):
        service = _service(conn)
        service.set_safe_to_spend_floor(amount=Amount(pence=2000))
        assert set(service.get_bank_graph_floor_values(year_month=AUGUST)) == {2000}

    def test_the_reserves_page_buffer_is_not_the_one_it_uses(self, conn):
        """Two buffers exist and they are not the same setting."""
        service = _service(conn)
        service.set_safe_to_spend_floor(amount=Amount(pence=2000))
        service.set_recommendation_buffer(enabled=True, amount=Amount(pence=99999))
        assert set(service.get_bank_graph_floor_values(year_month=AUGUST)) == {2000}

    def test_a_commitment_lifts_the_floor_as_its_due_date_nears(self, conn):
        service = _service(conn)
        service.set_safe_to_spend_floor(amount=Amount(pence=0))
        service.add_commitment(commitment=_commitment())
        values = service.get_bank_graph_floor_values(year_month=AUGUST)
        assert max(values) > 0
        # A ramp, not a step: what is held on the last day exceeds the first.
        assert values[-1] != values[0]


class TestWhatAMonthMustSetAside:
    """The whole-month figure the Solvency page states beside the bills.

    Read as at the month's FIRST day, so it describes the shape of the month
    rather than the moment it is read. That is what lets it sit beside "needs
    X more to hold flat", a figure that must not move as the month elapses.
    """

    def test_nothing_set_aside_costs_a_month_nothing(self, conn):
        service = _service(conn)
        assert service.get_month_reserve_cost_pence(year_month=AUGUST) == 0

    def test_a_budget_with_no_reserves_store_is_charged_nothing(self, conn):
        service = _service(conn, with_reserves=False)
        assert service.get_month_reserve_cost_pence(year_month=AUGUST) == 0

    def test_a_commitment_costs_the_month_what_it_has_to_find(self, conn):
        """August opens with the November bill four months out, so a quarter."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        cost = service.get_month_reserve_cost_pence(year_month=AUGUST)
        assert cost == monthly_rate_pence(_commitment(), AUGUST.first_day())
        assert cost > 0

    def test_the_figure_does_not_move_as_the_month_elapses(self, conn):
        """Two reads of the same month agree; only the month decides it."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        first = service.get_month_reserve_cost_pence(year_month=AUGUST)
        second = service.get_month_reserve_cost_pence(year_month=AUGUST)
        assert first == second

    def test_a_nearer_month_has_more_to_find(self, conn):
        """October is one month from the due date where August is three."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        august = service.get_month_reserve_cost_pence(year_month=AUGUST)
        october = service.get_month_reserve_cost_pence(
            year_month=YearMonth(year=2026, month=10)
        )
        assert october > august

    def test_two_commitments_are_added_together(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        one = service.get_month_reserve_cost_pence(year_month=AUGUST)
        service.add_commitment(commitment=_commitment(name="MOT"))
        assert service.get_month_reserve_cost_pence(year_month=AUGUST) == one * 2


class TestTheMonthGapCarriesTheReserve:
    """A month that pays every bill and sets nothing aside is not holding flat."""

    def test_setting_aside_raises_what_the_month_needs(self, conn):
        service = _service(conn)
        before = service.get_month_gap(year_month=AUGUST).needed_pence
        service.add_commitment(commitment=_commitment())
        after = service.get_month_gap(year_month=AUGUST)
        assert after.reserve_pence > 0
        assert after.needed_pence == before + after.reserve_pence

    def test_a_budget_setting_nothing_aside_reads_exactly_as_before(self, conn):
        assert _service(conn).get_month_gap(year_month=AUGUST).reserve_pence == 0
