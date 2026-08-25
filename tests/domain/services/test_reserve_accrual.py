"""Reserve accrual: what a commitment holds back, day by day.

The invariants at the bottom are swept exhaustively over real calendars
rather than sampled. Coverage proves a line ran; it says nothing about
whether the ramp is still monotonic when a leap day, a month-end due day and
a rolled cycle collide, which is what these sweeps are for.
"""

from datetime import date, timedelta

from clear_budget.domain.entities.commitment import Commitment
from clear_budget.domain.services.reserve_accrual import (
    accrued_pence,
    add_months,
    monthly_rate_pence,
    months_remaining,
    natural_rate_pence,
    occurrence_at,
    reserve_pence,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.recurrence import Recurrence
from clear_budget.domain.value_objects.year_month import YearMonth

AUGUST = YearMonth(year=2026, month=8)
FULL_PENCE = 62000


def _commitment(**overrides) -> Commitment:
    fields = {
        "id": 1,
        "name": "Car insurance",
        "amount": Amount(pence=FULL_PENCE),
        "due_date": date(2026, 11, 14),
        "recurrence": Recurrence.annual(),
        "created_month": AUGUST,
    }
    fields.update(overrides)
    return Commitment(**fields)


class TestAddMonths:
    def test_an_ordinary_step(self):
        assert add_months(date(2026, 1, 14), 1) == date(2026, 2, 14)

    def test_a_month_end_day_clamps_to_a_short_month(self):
        """The rule bills already follow for their due day."""
        assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)

    def test_it_clamps_to_a_leap_february(self):
        assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)

    def test_it_crosses_a_year(self):
        assert add_months(date(2026, 11, 14), 12) == date(2027, 11, 14)


class TestOccurrence:
    def test_nothing_is_reserved_before_the_commitment_exists(self):
        assert occurrence_at(_commitment(), date(2026, 7, 1)) is None

    def test_the_first_cycle_accrues_from_the_month_it_was_entered(self):
        occurrence = occurrence_at(_commitment(), date(2026, 9, 1))
        assert occurrence is not None
        assert occurrence.accrual_start == date(2026, 8, 1)
        assert occurrence.due == date(2026, 11, 14)

    def test_a_one_off_closes_for_good_on_its_day(self):
        once = _commitment(recurrence=Recurrence.once())
        assert occurrence_at(once, date(2026, 11, 14)) is None

    def test_a_repeat_rolls_to_the_next_cycle(self):
        occurrence = occurrence_at(_commitment(), date(2026, 11, 14))
        assert occurrence is not None
        assert occurrence.accrual_start == date(2026, 11, 14)
        assert occurrence.due == date(2027, 11, 14)

    def test_a_later_cycle_starts_empty(self):
        """Whatever was held went out with the payment."""
        held = _commitment(already_held=Amount(pence=5000))
        occurrence = occurrence_at(held, date(2027, 1, 1))
        assert occurrence is not None
        assert occurrence.held_pence == 0

    def test_it_rolls_across_several_missed_cycles(self):
        quarterly = _commitment(recurrence=Recurrence.every_months(3))
        occurrence = occurrence_at(quarterly, date(2027, 6, 1))
        assert occurrence is not None
        assert occurrence.due == date(2027, 8, 14)

    def test_an_ended_commitment_reserves_nothing(self):
        ended = _commitment(final_month=YearMonth(year=2026, month=9))
        assert occurrence_at(ended, date(2026, 10, 1)) is None


class TestTheRamp:
    def test_it_starts_at_what_is_already_held(self):
        held = _commitment(already_held=Amount(pence=3000))
        assert accrued_pence(held, date(2026, 8, 1)) == 3000

    def test_it_reaches_the_full_amount_exactly_on_the_due_day(self):
        assert accrued_pence(_commitment(), date(2026, 11, 14)) == FULL_PENCE

    def test_it_reserves_nothing_before_it_starts(self):
        assert accrued_pence(_commitment(), date(2026, 7, 1)) == 0

    def test_a_commitment_due_almost_at_once_owes_it_all_each_month(self):
        """Due in days with nothing held: the rate says so plainly."""
        late = _commitment(due_date=date(2026, 8, 3))
        assert monthly_rate_pence(late, date(2026, 8, 1)) == FULL_PENCE
        assert accrued_pence(late, date(2026, 8, 3)) == FULL_PENCE

    def test_a_window_with_no_days_in_it_is_owed_immediately(self):
        """Entered in the very month it falls due on the first of."""
        same_day = _commitment(due_date=date(2026, 8, 1))
        assert accrued_pence(same_day, date(2026, 8, 1)) == FULL_PENCE

    def test_over_holding_never_exceeds_the_amount(self):
        over = _commitment(already_held=Amount(pence=99999))
        assert reserve_pence(over, date(2026, 9, 1)) == FULL_PENCE


class TestTheReserve:
    def test_it_falls_to_nothing_on_the_day_the_money_leaves(self):
        assert reserve_pence(_commitment(), date(2026, 11, 14)) == 0

    def test_the_next_cycle_begins_accruing_from_that_day(self):
        assert reserve_pence(_commitment(), date(2026, 11, 15)) > 0

    def test_a_one_off_reserves_nothing_ever_again(self):
        once = _commitment(recurrence=Recurrence.once())
        assert reserve_pence(once, date(2027, 6, 1)) == 0

    def test_an_ended_commitment_reserves_nothing(self):
        ended = _commitment(final_month=YearMonth(year=2026, month=9))
        assert reserve_pence(ended, date(2026, 10, 1)) == 0


class TestRates:
    def test_the_monthly_rate_is_over_the_months_remaining(self):
        """Harsher than the natural rate, because the calendar is."""
        assert monthly_rate_pence(_commitment(), date(2026, 8, 1)) == 20667

    def test_the_natural_rate_is_what_it_settles_at(self):
        assert natural_rate_pence(_commitment()) == 5167

    def test_a_one_off_has_no_natural_rate_below_its_amount(self):
        once = _commitment(recurrence=Recurrence.once())
        assert natural_rate_pence(once) == FULL_PENCE

    def test_what_is_held_comes_off_the_rate(self):
        held = _commitment(already_held=Amount(pence=FULL_PENCE))
        assert monthly_rate_pence(held, date(2026, 8, 1)) == 0

    def test_a_closed_commitment_has_no_rate(self):
        once = _commitment(recurrence=Recurrence.once())
        assert monthly_rate_pence(once, date(2027, 1, 1)) == 0

    def test_months_remaining_is_never_less_than_one(self):
        """Due this month still has to be found this month."""
        assert months_remaining(_commitment(), date(2026, 11, 1)) == 1

    def test_months_remaining_counts_whole_months(self):
        assert months_remaining(_commitment(), date(2026, 8, 1)) == 3

    def test_a_closed_commitment_reports_a_single_month(self):
        once = _commitment(recurrence=Recurrence.once())
        assert months_remaining(once, date(2027, 1, 1)) == 1


class TestInvariants:
    """The properties from the brief, swept rather than sampled."""

    def test_the_ramp_never_falls_across_a_cycle(self):
        """Invariant 3: monotonically non-decreasing to the due day."""
        commitment = _commitment(already_held=Amount(pence=1500))
        day = date(2026, 8, 1)
        previous = -1
        while day <= date(2026, 11, 14):
            value = accrued_pence(commitment, day)
            assert value >= previous, day
            previous = value
            day += timedelta(days=1)

    def test_a_full_cycle_accrues_exactly_what_was_outstanding(self):
        """Invariant 4, at three different starting positions."""
        for held in (0, 1500, FULL_PENCE):
            commitment = _commitment(already_held=Amount(pence=held))
            start = accrued_pence(commitment, date(2026, 8, 1))
            end = accrued_pence(commitment, commitment.due_date)
            assert end == FULL_PENCE
            assert end - start == FULL_PENCE - min(held, FULL_PENCE)

    def test_the_reserve_is_zero_on_every_due_day_of_a_long_repeat(self):
        """Invariant 3's second half, over four rolled cycles."""
        quarterly = _commitment(recurrence=Recurrence.every_months(3))
        due = quarterly.due_date
        for _ in range(4):
            assert reserve_pence(quarterly, due) == 0
            assert accrued_pence(quarterly, due) == FULL_PENCE
            due = add_months(due, 3)

    def test_a_month_end_due_day_survives_every_short_month(self):
        """A 31st commitment rolled through February and the 30-day months."""
        monthly = _commitment(
            due_date=date(2026, 1, 31),
            recurrence=Recurrence.every_months(1),
            created_month=YearMonth(year=2025, month=12),
        )
        day = date(2026, 1, 1)
        while day <= date(2027, 1, 1):
            assert reserve_pence(monthly, day) >= 0
            assert accrued_pence(monthly, day) <= FULL_PENCE
            day += timedelta(days=1)
