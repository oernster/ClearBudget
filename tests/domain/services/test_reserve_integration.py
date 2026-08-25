"""Reserves meeting Safe to Spend: the properties the brief asks for.

These are the invariants that could not be stated until the floor actually
drove the headline figure. They are swept over whole projections rather than
sampled, because the interesting failures are at a boundary: the due day, the
month edge, the day a reserve overtakes the balance.
"""

from datetime import date, timedelta

from clear_budget.domain.entities.commitment import Commitment
from clear_budget.domain.services.reserve_floor import ReserveFloor
from clear_budget.domain.services.safe_to_spend import (
    DayProjection,
    sustainable_spend,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.recurrence import Recurrence
from clear_budget.domain.value_objects.year_month import YearMonth

TODAY = date(2026, 8, 25)
AUGUST = YearMonth(year=2026, month=8)
BUFFER_PENCE = 15000
PREMIUM_PENCE = 62000
OPENING_PENCE = 300000
DUE_DAY = date(2026, 10, 14)


def _flat_projection(*, days: int = 120, opening: int = OPENING_PENCE):
    """A steady balance, so any movement in the answer comes from the floor."""
    return [
        DayProjection(day=TODAY + timedelta(days=offset), balance_pence=opening)
        for offset in range(days)
    ]


def _projection_paying_on(due: date, amount: int, *, days: int = 120):
    """A steady balance that drops by `amount` on `due` and stays down."""
    return [
        DayProjection(
            day=TODAY + timedelta(days=offset),
            balance_pence=(
                OPENING_PENCE - amount
                if TODAY + timedelta(days=offset) >= due
                else OPENING_PENCE
            ),
        )
        for offset in range(days)
    ]


def _commitment(**overrides) -> Commitment:
    fields = {
        "id": 1,
        "name": "Car insurance",
        "amount": Amount(pence=PREMIUM_PENCE),
        "due_date": DUE_DAY,
        "recurrence": Recurrence.annual(),
        "created_month": AUGUST,
    }
    fields.update(overrides)
    return Commitment(**fields)


def _spend(projection, floor):
    return sustainable_spend(projection=projection, today=TODAY, floor=floor)


class TestInvariantOne:
    """Adding a commitment never raises Safe to Spend Today."""

    def test_the_figure_falls_or_holds_when_something_is_set_aside(self):
        projection = _flat_projection()
        bare = _spend(projection, ReserveFloor.flat(BUFFER_PENCE))
        with_one = _spend(
            projection,
            ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(_commitment(),)),
        )
        assert with_one.amount_pence <= bare.amount_pence

    def test_it_holds_across_every_start_day_of_a_long_window(self):
        """Swept, because the binding day moves as the reserve grows."""
        projection = _flat_projection(days=200)
        bare = _spend(projection, ReserveFloor.flat(BUFFER_PENCE))
        for day_offset in range(0, 200, 7):
            due = TODAY + timedelta(days=day_offset + 1)
            floor = ReserveFloor(
                buffer_pence=BUFFER_PENCE,
                commitments=(_commitment(due_date=due),),
            )
            assert _spend(projection, floor).amount_pence <= bare.amount_pence, due


class TestInvariantTwo:
    """Removing a commitment never lowers it."""

    def test_dropping_one_of_two_never_costs_headroom(self):
        projection = _flat_projection()
        second = _commitment(id=2, name="Christmas", due_date=date(2026, 12, 20))
        both = ReserveFloor(
            buffer_pence=BUFFER_PENCE, commitments=(_commitment(), second)
        )
        one = ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(_commitment(),))
        assert (
            _spend(projection, one).amount_pence
            >= _spend(projection, both).amount_pence
        )


class TestInvariantFive:
    """The due day nets out: the reserve leaves exactly as the money does."""

    def test_headroom_on_the_due_day_is_untouched_by_the_reserve(self):
        projection = _projection_paying_on(DUE_DAY, PREMIUM_PENCE)
        bare = ReserveFloor.flat(BUFFER_PENCE)
        with_one = ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(_commitment(),))
        due_balance = next(d.balance_pence for d in projection if d.day == DUE_DAY)
        assert due_balance - bare.at(DUE_DAY) == due_balance - with_one.at(DUE_DAY)

    def test_the_floor_returns_to_the_buffer_on_the_day_it_is_paid(self):
        floor = ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(_commitment(),))
        assert floor.at(DUE_DAY - timedelta(days=1)) > BUFFER_PENCE
        assert floor.at(DUE_DAY) == BUFFER_PENCE

    def test_a_commitment_beyond_the_horizon_is_still_felt_today(self):
        """The whole point: a distant bill is visible without a longer window."""
        projection = _flat_projection()
        far = _commitment(due_date=date(2027, 6, 1))
        bare = _spend(projection, ReserveFloor.flat(BUFFER_PENCE))
        with_far = _spend(
            projection,
            ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(far,)),
        )
        assert with_far.amount_pence < bare.amount_pence


class TestWhatTheResultReports:
    def test_the_floor_is_reported_as_it_stood_on_the_binding_day(self):
        projection = _flat_projection()
        floor = ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(_commitment(),))
        result = _spend(projection, floor)
        assert result.floor_pence == floor.at(result.binding_day)

    def test_the_reserved_part_is_named_separately(self):
        """So a caller can say what constrained the day, not just how much."""
        projection = _flat_projection()
        floor = ReserveFloor(buffer_pence=BUFFER_PENCE, commitments=(_commitment(),))
        result = _spend(projection, floor)
        assert result.reserved_pence == floor.reserved_at(result.binding_day)
        assert result.floor_pence == BUFFER_PENCE + result.reserved_pence

    def test_a_flat_floor_reserves_nothing(self):
        result = _spend(_flat_projection(), ReserveFloor.flat(BUFFER_PENCE))
        assert result.reserved_pence == 0
        assert result.floor_pence == BUFFER_PENCE
