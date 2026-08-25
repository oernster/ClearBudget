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
_TODAY = date(2026, 8, 15)
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


class TestWhatAMonthActuallyHeld:
    """The archive's own reading: what was held when that month closed.

    Historical, never a projection. An archived month must report the reserve
    it really carried, so the figure is evaluated at that month's last day and
    a commitment that has since stopped still counts for the months it covered.
    """

    def test_a_budget_with_no_commitments_held_nothing(self, conn):
        assert _service(conn).get_reserve_held_pence(year_month=AUGUST) == 0

    def test_a_month_before_the_commitment_started_held_nothing(self, conn):
        """History is never fabricated backwards."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        earlier = YearMonth(year=2026, month=6)
        assert service.get_reserve_held_pence(year_month=earlier) == 0

    def test_a_month_partway_through_holds_part_of_it(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        held = service.get_reserve_held_pence(year_month=AUGUST)
        assert 0 < held < FULL_PENCE

    def test_a_later_month_holds_more_than_an_earlier_one(self, conn):
        """The ramp, read at two different closes."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        august = service.get_reserve_held_pence(year_month=AUGUST)
        october = service.get_reserve_held_pence(
            year_month=YearMonth(year=2026, month=10)
        )
        assert october > august

    def test_the_due_month_drops_to_what_the_next_cycle_has_begun(self, conn):
        """The money went; a repeat then starts saving again the same day.

        So the archive shows a fall rather than a zero, which is what really
        happened: by the close of the due month a fortnight of the NEXT year's
        premium has already been put by.
        """
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        october = service.get_reserve_held_pence(
            year_month=YearMonth(year=2026, month=10)
        )
        november = service.get_reserve_held_pence(year_month=NOVEMBER)
        assert november < october
        assert november < FULL_PENCE // 10

    def test_a_one_off_closes_its_due_month_holding_nothing(self, conn):
        """Nothing repeats, so nothing starts again."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment(recurrence=Recurrence.once()))
        assert service.get_reserve_held_pence(year_month=NOVEMBER) == 0

    def test_the_reading_does_not_move_when_it_is_taken(self, conn):
        """An archived figure that drifted would rewrite the past."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        first = service.get_reserve_held_pence(year_month=AUGUST)
        assert service.get_reserve_held_pence(year_month=AUGUST) == first

    def test_a_commitment_since_ended_still_counts_for_the_months_it_covered(
        self, conn
    ):
        """Ending sets a final month rather than erasing what really happened."""
        service = _service(conn)
        stored = service.add_commitment(commitment=_commitment())
        before = service.get_reserve_held_pence(year_month=AUGUST)
        service.end_commitment(
            commitment_id=stored.id, final_month=YearMonth(year=2026, month=9)
        )
        assert service.get_reserve_held_pence(year_month=AUGUST) == before

    def test_a_month_after_it_ended_holds_nothing(self, conn):
        service = _service(conn)
        stored = service.add_commitment(commitment=_commitment())
        service.end_commitment(
            commitment_id=stored.id, final_month=YearMonth(year=2026, month=9)
        )
        assert (
            service.get_reserve_held_pence(year_month=YearMonth(year=2026, month=10))
            == 0
        )

    def test_two_commitments_are_added_together(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        one = service.get_reserve_held_pence(year_month=AUGUST)
        service.add_commitment(commitment=_commitment(name="MOT"))
        assert service.get_reserve_held_pence(year_month=AUGUST) == one * 2

    def test_the_emergency_buffer_is_not_part_of_it(self, conn):
        """The column reports what was set ASIDE, never the safety net."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        without = service.get_reserve_held_pence(year_month=AUGUST)
        service.set_recommendation_buffer(enabled=True, amount=Amount(pence=99999))
        assert service.get_reserve_held_pence(year_month=AUGUST) == without


class TestWhereThatLeavesEachMonth:
    """The Reserves page's per-month block, plus the invariant behind it.

    Brief section 9, invariant 7: the Reserves page's per-month figures equal
    the Solvency bank page's for the same months. It holds by construction
    rather than by care, because both read the one month walk from the one
    opening; these tests are what stops that quietly ceasing to be true.
    """

    def test_it_returns_one_line_per_month_asked_for(self, conn):
        lines = _service(conn).get_reserve_month_lines(months=3, today=_TODAY)
        assert len(lines) == 3

    def test_the_months_start_after_the_current_one(self, conn):
        """The current month is mostly behind or committed; ahead is the point."""
        lines = _service(conn).get_reserve_month_lines(months=2, today=_TODAY)
        assert [line.year_month.month for line in lines] == [9, 10]

    def test_with_nothing_set_aside_the_floor_is_the_buffer(self, conn):
        service = _service(conn)
        service.set_recommendation_buffer(enabled=True, amount=Amount(pence=15000))
        for line in service.get_reserve_month_lines(months=2, today=_TODAY):
            assert line.floor_pence == 15000

    def test_a_commitment_lifts_the_floor_above_the_buffer(self, conn):
        service = _service(conn)
        service.set_recommendation_buffer(enabled=True, amount=Amount(pence=15000))
        service.add_commitment(commitment=_commitment())
        for line in service.get_reserve_month_lines(months=2, today=_TODAY):
            assert line.floor_pence > 15000

    def test_what_is_clear_is_the_low_less_the_floor(self, conn):
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        for line in service.get_reserve_month_lines(months=3, today=_TODAY):
            assert line.clear_pence == line.low_pence - line.floor_pence

    def test_a_month_that_cannot_cover_its_floor_reads_as_short(self, conn):
        service = _service(conn)
        service.set_recommendation_buffer(enabled=True, amount=Amount(pence=99_999_00))
        for line in service.get_reserve_month_lines(months=1, today=_TODAY):
            assert line.is_short
            assert line.clear_pence < 0

    def test_a_month_that_covers_it_does_not(self, conn):
        service = _service(conn)
        for line in service.get_reserve_month_lines(months=1, today=_TODAY):
            assert not line.is_short

    def test_invariant_seven_the_lows_match_the_solvency_bank_page(self, conn):
        """The same months, the same lows, the same days they fall on.

        Solvency chains its forward months from this month's projected end
        through the same walk. Reading them side by side is the only way to
        know the two pages agree rather than merely look as though they do.
        """
        from clear_budget.application.services._month_walk import walk_month

        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        lines = service.get_reserve_month_lines(months=3, today=_TODAY)

        current = YearMonth(year=_TODAY.year, month=_TODAY.month)
        balance = service.get_projected_month_end_balance_pence(
            year_month=current,
            summary=service.get_month_summary(year_month=current),
        )
        cursor = current
        for line in lines:
            cursor = cursor.next_month()
            walk = walk_month(balance, service.get_month_summary(year_month=cursor))
            assert line.year_month == cursor
            assert line.low_pence == walk["min_balance"]
            assert line.low_day == walk["min_day"]
            balance = walk["closing"]

    def test_the_floor_is_read_on_the_day_the_low_falls(self, conn):
        """The tightest point of the month is where the answer holds or does not."""
        service = _service(conn)
        service.add_commitment(commitment=_commitment())
        floor = service.get_reserve_floor()
        for line in service.get_reserve_month_lines(months=3, today=_TODAY):
            binding = date(
                line.year_month.year, line.year_month.month, max(1, line.low_day)
            )
            assert line.floor_pence == floor.at(binding)
