"""Tests for the recommendations engine.

Every scenario asserts against a hand-computed day-by-day simulation, because
the engine's promise is that each suggestion is a measurement. The branch map
is exhaustive on purpose: each candidate rejection (immovable, past the low
day, at or after the last income, no income at all) has a test that plants
exactly that shape and expects the engine to fall through to the ask.
"""

from clear_budget.domain.services.recommendations import (
    KIND_BILL,
    KIND_INCOME,
    PlannedItem,
    PlannedMonth,
    TrialDay,
    immovable_months,
    recommend,
    retimed_months,
)

_DAYS = 30


def _bill(name: str, day: int, pence: int, movable: bool = False) -> PlannedItem:
    return PlannedItem(
        name=name, kind=KIND_BILL, day=day, amount_pence=-pence, movable=movable
    )


def _income(name: str, day: int, pence: int, movable: bool = False) -> PlannedItem:
    return PlannedItem(
        name=name, kind=KIND_INCOME, day=day, amount_pence=pence, movable=movable
    )


def _month(*items: PlannedItem, year: int = 2026, month: int = 9) -> PlannedMonth:
    return PlannedMonth(year=year, month=month, days=_DAYS, items=tuple(items))


def _recommend(months, opening=0, overdraft=0, buffer=0):
    return recommend(
        months=tuple(months),
        opening_balance_pence=opening,
        overdraft_limit_pence=overdraft,
        buffer_pence=buffer,
    )


class TestHealthyPlan:
    """A plan that already clears the target needs nothing."""

    def test_healthy_months_yield_outlook_only(self) -> None:
        first = _month(_income("Pay", 1, 100000), _bill("Rent", 20, 50000))
        empty = _month(month=10)  # a month with no entries at all
        result = _recommend([first, empty])
        assert result.healthy
        assert result.moves == ()
        assert result.asks == ()
        assert result.extras == ()
        assert [(m.low_pence, m.low_day, m.close_pence) for m in result.outlook] == [
            (0, 1, 50000),
            (50000, 1, 50000),
        ]

    def test_a_healthy_plan_still_offers_headroom(self) -> None:
        plan = _month(_income("Pay", 20, 100000), _bill("Rent", 5, 30000, True))
        result = _recommend([plan], opening=50000)
        # The month clears as entered (low 20000 on day 5), so nothing is
        # needed; moving Rent past payday is still measured and offered.
        assert result.healthy
        (extra,) = result.extras
        assert (extra.name, extra.from_day, extra.to_day) == ("Rent", 5, 21)
        assert (extra.low_before_pence, extra.low_after_pence) == (20000, 50000)

    def test_close_chains_between_months(self) -> None:
        first = _month(_income("Pay", 1, 100000), _bill("Rent", 10, 40000))
        second = _month(_bill("Fee", 5, 30000), month=10)
        result = _recommend([first, second], opening=10000)
        # First: 10000 -> 110000 -> 70000; second opens at 70000.
        assert [(m.low_pence, m.low_day, m.close_pence) for m in result.outlook] == [
            (10000, 1, 70000),
            (40000, 5, 40000),
        ]


class TestBillMove:
    def test_movable_bill_moves_past_last_income(self) -> None:
        plan = _month(_income("Pay", 20, 100000), _bill("Rent", 5, 80000, True))
        result = _recommend([plan])
        assert not result.healthy
        assert result.asks == ()
        (move,) = result.moves
        assert (move.name, move.kind) == ("Rent", KIND_BILL)
        assert (move.from_day, move.to_day) == (5, 21)
        assert (move.low_before_pence, move.low_after_pence) == (-80000, 0)
        assert [(m.low_pence, m.low_day, m.close_pence) for m in result.outlook] == [
            (0, 1, 20000)
        ]

    def test_better_candidate_wins_whatever_the_order(self) -> None:
        plan = _month(
            _income("Pay", 20, 100000),
            _bill("Small", 5, 10000, True),
            _bill("Big", 5, 60000, True),
        )
        result = _recommend([plan])
        # Moving Big lifts the low to -10000; moving Small only to -60000.
        assert result.moves[0].name == "Big"

    def test_tie_resolves_by_name_stably(self) -> None:
        plan = _month(
            _income("Pay", 20, 100000),
            _bill("B", 5, 30000, True),
            _bill("A", 5, 30000, True),
        )
        result = _recommend([plan])
        # Equal lift either way; the greater name wins and keeps winning, so
        # the order of moves is the same run to run.
        assert [m.name for m in result.moves] == ["B", "A"]
        assert result.asks == ()


class TestIncomeMove:
    def test_movable_income_moves_to_day_one(self) -> None:
        plan = _month(_bill("Rent", 10, 40000), _income("Pay", 25, 100000, True))
        result = _recommend([plan])
        (move,) = result.moves
        assert (move.name, move.kind) == ("Pay", KIND_INCOME)
        assert (move.from_day, move.to_day) == (25, 1)
        assert (move.low_before_pence, move.low_after_pence) == (-40000, 0)
        assert result.asks == ()


class TestSkippedCandidates:
    """Shapes where no move can help; the shortfall becomes the ask."""

    def test_immovable_items_are_never_moved(self) -> None:
        plan = _month(_bill("Rent", 10, 50000), _income("Pay", 20, 30000))
        result = _recommend([plan])
        assert result.moves == ()
        (ask,) = result.asks
        assert (ask.amount_pence, ask.by_day) == (50000, 10)
        assert [(m.low_pence, m.low_day, m.close_pence) for m in result.outlook] == [
            (0, 10, 30000)
        ]
        # The clamped low assumes the ask found; the unaided low is where
        # the month would bottom out on its own.
        assert result.outlook[0].unaided_low_pence == -50000

    def test_movable_bill_after_the_low_day_is_skipped(self) -> None:
        plan = _month(
            _bill("Sink", 5, 50000),
            _income("Pay", 10, 100000),
            _bill("Late", 20, 10000, True),
        )
        result = _recommend([plan])
        # The dip is on day 5; Late is already past it, so moving it later
        # cannot help.
        assert result.moves == ()
        (ask,) = result.asks
        assert (ask.amount_pence, ask.by_day) == (50000, 5)

    def test_bill_already_after_last_income_is_skipped(self) -> None:
        plan = _month(_income("Pay", 10, 100000), _bill("Rent", 20, 150000, True))
        result = _recommend([plan])
        assert result.moves == ()
        (ask,) = result.asks
        assert (ask.amount_pence, ask.by_day) == (50000, 20)

    def test_month_with_no_income_cannot_retime_bills(self) -> None:
        plan = _month(_bill("Rent", 10, 50000, True))
        result = _recommend([plan])
        assert result.moves == ()
        (ask,) = result.asks
        assert (ask.amount_pence, ask.by_day) == (50000, 10)

    def test_move_with_no_measured_lift_is_not_emitted(self) -> None:
        plan = _month(
            _bill("A", 3, 5000, True),
            _income("Pay", 10, 10000),
            _bill("B", 15, 10000),
        )
        result = _recommend([plan])
        # Moving A past day 10 leaves the low at -5000 either way (it just
        # relocates from day 3 to day 15), so the engine must not propose it.
        assert result.moves == ()
        (ask,) = result.asks
        assert (ask.amount_pence, ask.by_day) == (5000, 3)


class TestRetimedMonths:
    """The try-it-on transform: pure, item-keyed and movability-guarded."""

    def test_no_trials_returns_the_months_unchanged(self) -> None:
        months = (_month(_bill("Rent", 10, 50000, True)),)
        assert retimed_months(months, ()) is months

    def test_a_trial_moves_its_item_in_every_month(self) -> None:
        months = (
            _month(_bill("Rent", 10, 50000, True), _income("Pay", 20, 60000)),
            _month(_bill("Rent", 10, 50000, True), month=10),
        )
        moved = retimed_months(months, (TrialDay(KIND_BILL, "Rent", 21),))
        assert [i.day for m in moved for i in m.items if i.name == "Rent"] == [21, 21]
        # Everything untried is untouched.
        assert [i.day for i in moved[0].items if i.name == "Pay"] == [20]

    def test_an_immovable_item_ignores_its_trial(self) -> None:
        months = (_month(_bill("Rent", 10, 50000)),)
        moved = retimed_months(months, (TrialDay(KIND_BILL, "Rent", 21),))
        assert moved[0].items[0].day == 10

    def test_the_trial_day_is_capped_at_the_month_length(self) -> None:
        short = PlannedMonth(
            year=2027,
            month=2,
            days=28,
            items=(_bill("Rent", 10, 50000, True),),
        )
        moved = retimed_months((short,), (TrialDay(KIND_BILL, "Rent", 31),))
        assert moved[0].items[0].day == 28

    def test_pinned_months_yield_the_plan_free_reading(self) -> None:
        plan = _month(_income("Pay", 20, 100000), _bill("Rent", 5, 80000, True))
        result = _recommend(list(immovable_months((plan,))))
        # Rent could move; pinned, the engine may not say so: the shortfall
        # becomes the ask and no move or extra is proposed.
        assert result.moves == ()
        assert result.extras == ()
        (ask,) = result.asks
        assert (ask.amount_pence, ask.by_day) == (80000, 5)

    def test_a_trial_feeds_straight_into_the_engine(self) -> None:
        plan = _month(_income("Pay", 20, 100000), _bill("Rent", 5, 80000, True))
        tried = retimed_months((plan,), (TrialDay(KIND_BILL, "Rent", 21),))
        result = _recommend(list(tried))
        # The retiming is already in the months, so nothing is proposed and
        # the outlook shows its effect.
        assert result.healthy
        assert [(m.low_pence, m.low_day) for m in result.outlook] == [(0, 1)]


class TestAsks:
    def test_asks_are_incremental_across_months(self) -> None:
        first = _month(_bill("Rent", 10, 50000), _income("Pay", 20, 20000))
        second = _month(_bill("Rent", 10, 50000), month=10)
        result = _recommend([first, second])
        assert [(a.amount_pence, a.by_day) for a in result.asks] == [
            (50000, 10),
            (30000, 10),
        ]
        # Each month's outlook already assumes its ask arrived.
        assert [(m.low_pence, m.close_pence) for m in result.outlook] == [
            (0, 20000),
            (0, 0),
        ]

    def test_overdraft_floor_and_buffer_shape_the_target(self) -> None:
        plan = _month(_bill("Rent", 10, 50000))
        with_floor = _recommend([plan], overdraft=20000)
        (ask,) = with_floor.asks
        assert ask.amount_pence == 30000
        with_buffer = _recommend([plan], overdraft=20000, buffer=10000)
        (ask,) = with_buffer.asks
        assert ask.amount_pence == 40000

    def test_extras_never_duplicate_a_mandatory_move(self) -> None:
        plan = _month(
            _income("Pay", 20, 100000),
            _bill("Rent", 5, 80000, True),
            _bill("Sub", 12, 5000, True),
        )
        result = _recommend([plan], opening=10000)
        # Moving Rent alone clears the month (low 5000 on day 12), so only
        # Rent is mandatory; Sub's remaining lift is offered as the extra
        # and Rent is not offered twice.
        (move,) = result.moves
        assert move.name == "Rent"
        (extra,) = result.extras
        assert (extra.name, extra.from_day, extra.to_day) == ("Sub", 12, 21)
        assert (extra.low_before_pence, extra.low_after_pence) == (5000, 10000)

    def test_an_ask_month_has_no_extras(self) -> None:
        plan = _month(_income("Pay", 20, 30000), _bill("Rent", 10, 50000))
        result = _recommend([plan])
        # An ask changes every day's balance equally, so it changes no move
        # candidate: any lifting move would already have been taken as
        # mandatory before asking. A month that asks therefore offers none.
        (ask,) = result.asks
        assert result.extras == ()

    def test_moves_and_ask_chain_in_one_month(self) -> None:
        plan = _month(
            _income("Pay", 20, 50000),
            _bill("Rent", 5, 60000, True),
            _bill("Fee", 5, 30000),
        )
        result = _recommend([plan])
        # Rent moves past payday, which lifts the low from -90000 on day 5 to
        # -40000 on day 21; Fee cannot move, so that remainder is asked for.
        (move,) = result.moves
        assert move.name == "Rent"
        assert (move.low_before_pence, move.low_after_pence) == (-90000, -40000)
        (ask,) = result.asks
        assert (ask.amount_pence, ask.by_day) == (40000, 21)
        assert [(m.low_pence, m.low_day, m.close_pence) for m in result.outlook] == [
            (0, 21, 0)
        ]
