"""The floor: what the projection refuses to call spendable, day by day.

The sweep at the bottom is the one that protects every existing budget. A
floor built with nothing set aside has to answer the plain buffer on every
day; otherwise an upgrade quietly restates figures the user has read.
"""

from datetime import date, timedelta

from clear_budget.domain.entities.commitment import Commitment
from clear_budget.domain.services.reserve_floor import ReserveFloor
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.recurrence import Recurrence
from clear_budget.domain.value_objects.year_month import YearMonth

AUGUST = YearMonth(year=2026, month=8)
BUFFER_PENCE = 15000
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


class TestAFlatFloor:
    def test_it_is_the_buffer_and_nothing_else(self):
        assert ReserveFloor.flat(BUFFER_PENCE).at(date(2026, 9, 1)) == BUFFER_PENCE

    def test_it_knows_it_is_flat(self):
        assert ReserveFloor.flat(BUFFER_PENCE).is_flat

    def test_it_reserves_nothing(self):
        assert ReserveFloor.flat(BUFFER_PENCE).reserved_at(date(2026, 9, 1)) == 0


class TestCommitmentsRaiseIt:
    def test_the_floor_carries_the_buffer_and_the_reserve(self):
        floor = ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(_commitment(),))
        day = date(2026, 9, 1)
        assert floor.at(day) == BUFFER_PENCE + floor.reserved_at(day)

    def test_it_climbs_as_the_due_day_approaches(self):
        floor = ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(_commitment(),))
        assert floor.at(date(2026, 11, 13)) > floor.at(date(2026, 9, 1))

    def test_it_falls_back_to_the_buffer_when_the_money_leaves(self):
        """The reserve and the outflow are the same money, so they net out."""
        floor = ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(_commitment(),))
        assert floor.at(date(2026, 11, 14)) == BUFFER_PENCE

    def test_several_commitments_add_up(self):
        second = _commitment(id=2, name="Boiler service", amount=Amount(pence=11000))
        one = ReserveFloor(buffer_pence=0, commitments=(_commitment(),))
        both = ReserveFloor(buffer_pence=0, commitments=(_commitment(), second))
        day = date(2026, 10, 1)
        assert both.at(day) > one.at(day)

    def test_a_floor_with_commitments_is_not_flat(self):
        floor = ReserveFloor(buffer_pence=0, commitments=(_commitment(),))
        assert not floor.is_flat


class TestEverydaySpending:
    def test_unset_holds_nothing_back(self):
        """Phase one ships it visible and unset, never assumed to be zero."""
        floor = ReserveFloor(buffer_pence=0, variable_spend_monthly_pence=None)
        assert floor.at(date(2026, 9, 10)) == 0

    def test_zero_holds_nothing_back(self):
        floor = ReserveFloor(buffer_pence=0, variable_spend_monthly_pence=0)
        assert floor.at(date(2026, 9, 10)) == 0

    def test_the_whole_month_is_held_on_the_first(self):
        floor = ReserveFloor(buffer_pence=0, variable_spend_monthly_pence=30000)
        assert floor.at(date(2026, 9, 1)) == 30000

    def test_it_burns_down_across_the_month(self):
        floor = ReserveFloor(buffer_pence=0, variable_spend_monthly_pence=30000)
        assert floor.at(date(2026, 9, 30)) == 1000

    def test_today_is_still_to_come(self):
        """Today's shopping has not happened yet, so today is still held."""
        floor = ReserveFloor(buffer_pence=0, variable_spend_monthly_pence=30000)
        assert floor.variable_pence_at(date(2026, 9, 30)) > 0

    def test_a_floor_with_everyday_spending_is_not_flat(self):
        floor = ReserveFloor(buffer_pence=0, variable_spend_monthly_pence=30000)
        assert not floor.is_flat


class TestInvariants:
    def test_an_untouched_budget_projects_exactly_as_before(self):
        """Invariant 6, swept over a year rather than sampled."""
        floor = ReserveFloor.flat(BUFFER_PENCE)
        day = date(2026, 1, 1)
        while day <= date(2027, 1, 1):
            assert floor.at(day) == BUFFER_PENCE, day
            day += timedelta(days=1)

    def test_setting_something_aside_never_lowers_the_floor(self):
        """Invariant 1 in its domain form: a reserve only ever holds more."""
        bare = ReserveFloor.flat(BUFFER_PENCE)
        with_one = ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(_commitment(),))
        day = date(2026, 8, 1)
        while day <= date(2027, 12, 31):
            assert with_one.at(day) >= bare.at(day), day
            day += timedelta(days=1)

    def test_removing_a_commitment_never_raises_the_floor(self):
        """Invariant 2, the same sweep read the other way round."""
        second = _commitment(id=2, name="Christmas", due_date=date(2026, 12, 20))
        both = ReserveFloor(
            buffer_pence=BUFFER_PENCE, commitments=(_commitment(), second)
        )
        one = ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(_commitment(),))
        day = date(2026, 8, 1)
        while day <= date(2027, 12, 31):
            assert one.at(day) <= both.at(day), day
            day += timedelta(days=1)

    def test_the_floor_never_goes_below_the_buffer(self):
        """However the commitments are shaped, the buffer is the minimum."""
        over_held = _commitment(already_held=Amount(pence=99999))
        floor = ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(over_held,))
        day = date(2026, 8, 1)
        while day <= date(2027, 12, 31):
            assert floor.at(day) >= BUFFER_PENCE, day
            day += timedelta(days=1)
