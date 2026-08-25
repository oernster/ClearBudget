"""Tests for the third lever: pausing a reserve, priced rather than encouraged.

The danger this lever carries is that it always LOOKS like a win. The relief
lands inside the window on screen; the bill it was for lands later, sometimes
outside the window entirely. So every test here is really one question: does
the suggestion state its own cost; does it stay quiet when there is no
trouble for it to relieve.
"""

from clear_budget.domain.services.recommendations import (
    KIND_BILL,
    KIND_INCOME,
    PlannedItem,
    PlannedMonth,
    PlannedReserve,
    TrialPause,
    paused_months,
    recommend,
)

_SALARY_PENCE = 120000
_RENT_PENCE = 110000
_OPENING_PENCE = 60000
# 400.00 for Christmas, put by at 100.00 a month.
_AMOUNT_PENCE = 40000
_RATE_PENCE = 10000
_OCTOBER, _NOVEMBER, _DECEMBER = 10, 11, 12
_YEAR = 2026
_DAYS = {_OCTOBER: 31, _NOVEMBER: 30, _DECEMBER: 31}
# Months put by before each horizon month opens; December is the due month, so
# the reserve has fallen to nothing by then.
_MONTHS_IN = {_OCTOBER: 2, _NOVEMBER: 3, _DECEMBER: 0}


def _month(month: int, *, reserved: bool = True) -> PlannedMonth:
    days = _DAYS[month]
    held = _RATE_PENCE * _MONTHS_IN[month] if reserved else 0
    return PlannedMonth(
        year=_YEAR,
        month=month,
        days=days,
        items=(
            PlannedItem("Salary", KIND_INCOME, 25, _SALARY_PENCE, False),
            PlannedItem("Rent", KIND_BILL, 1, -_RENT_PENCE, False),
        ),
        reserve_by_day=tuple(held for _ in range(days)),
    )


def _months(*, reserved: bool = True) -> tuple[PlannedMonth, ...]:
    return tuple(
        _month(month, reserved=reserved) for month in (_OCTOBER, _NOVEMBER, _DECEMBER)
    )


def _reserve(*, due_month: int = _DECEMBER) -> PlannedReserve:
    return PlannedReserve(
        name="Christmas",
        amount_pence=_AMOUNT_PENCE,
        by_day=tuple(
            tuple(_RATE_PENCE * _MONTHS_IN[month] for _ in range(_DAYS[month]))
            for month in (_OCTOBER, _NOVEMBER, _DECEMBER)
        ),
        due_year=_YEAR,
        due_month=due_month,
    )


def _run(*, months=None, reserves=None, opening=_OPENING_PENCE, buffer_pence=0):
    return recommend(
        months=_months() if months is None else months,
        opening_balance_pence=opening,
        overdraft_limit_pence=0,
        buffer_pence=buffer_pence,
        reserves=(_reserve(),) if reserves is None else reserves,
    )


class TestWhenNothingIsProposed:
    def test_a_budget_setting_nothing_aside_gets_no_pause(self):
        assert _run(months=_months(reserved=False), reserves=()).pauses == ()

    def test_a_window_that_already_clears_gets_no_pause(self):
        """No trouble to relieve, so stopping a reserve is cost with no benefit."""
        assert _run(opening=10_000_00).pauses == ()

    def test_a_reserve_that_lifts_nothing_is_not_emitted(self):
        """The same rule the retimings obey: no measured lift, no suggestion."""
        idle = PlannedReserve(
            name="Nothing yet",
            amount_pence=_AMOUNT_PENCE,
            by_day=tuple(tuple(0 for _ in range(_DAYS[m])) for m in _DAYS),
            due_year=_YEAR,
            due_month=_DECEMBER,
        )
        assert _run(reserves=(idle,)).pauses == ()


class TestThePricedSuggestion:
    def test_one_pause_is_offered_for_the_commitment(self):
        pauses = _run().pauses
        assert len(pauses) == 1
        assert pauses[0].name == "Christmas"

    def test_it_starts_from_the_first_month_in_trouble(self):
        """Pausing earlier costs more and buys nothing: October is the first."""
        pause = _run().pauses[0]
        assert (pause.from_year, pause.from_month) == (_YEAR, _OCTOBER)

    def test_it_names_every_month_it_lifts(self):
        pause = _run().pauses[0]
        assert [lift.month for lift in pause.lifts] == [_OCTOBER, _NOVEMBER]

    def test_each_lift_is_measured_both_ways(self):
        pause = _run().pauses[0]
        for lift in pause.lifts:
            assert lift.low_after_pence > lift.low_before_pence

    def test_the_lift_figures_match_the_outlook_printed_above_them(self):
        """A sentence quoting a low the page does not show is a bug in the page."""
        result = _run()
        unaided = {month.month: month.unaided_low_pence for month in result.outlook}
        for lift in result.pauses[0].lifts:
            assert lift.low_before_pence == unaided[lift.month]

    def test_it_states_what_the_due_month_arrives_short_by(self):
        """The whole amount less what was already put by when the pause starts."""
        pause = _run().pauses[0]
        already_held = _RATE_PENCE * _MONTHS_IN[_OCTOBER]
        assert pause.shortfall_pence == _AMOUNT_PENCE - already_held

    def test_a_due_month_inside_the_window_is_marked_so(self):
        assert _run().pauses[0].due_within_horizon

    def test_a_due_month_beyond_the_window_is_marked_too(self):
        """The case where the page would show all the relief and none of the cost."""
        beyond = _reserve(due_month=_DECEMBER)
        beyond = PlannedReserve(
            name=beyond.name,
            amount_pence=beyond.amount_pence,
            by_day=beyond.by_day,
            due_year=_YEAR + 1,
            due_month=3,
        )
        assert not _run(reserves=(beyond,)).pauses[0].due_within_horizon


class TestAPauseIsNeverARepair:
    def test_a_plan_needing_a_pause_is_still_not_healthy(self):
        """Stopping saving does not make a plan sound, so it must not read so."""
        result = _run()
        assert result.pauses
        assert not result.healthy

    def test_the_ask_is_unchanged_by_the_pause_being_available(self):
        """The engine's own repairs are what they were; the pause is an option."""
        with_reserves = _run()
        without = _run(reserves=())
        assert [a.amount_pence for a in with_reserves.asks] == [
            a.amount_pence for a in without.asks
        ]


class TestTryingOneOn:
    def test_a_trialled_pause_lifts_the_months_it_said_it_would(self):
        pause = _run().pauses[0]
        tried = paused_months(
            _months(),
            (_reserve(),),
            (TrialPause(name="Christmas", from_year=_YEAR, from_month=_OCTOBER),),
        )
        after = {
            month.month: month.unaided_low_pence
            for month in _run(months=tried, reserves=()).outlook
        }
        for lift in pause.lifts:
            assert after[lift.month] == lift.low_after_pence

    def test_a_pause_naming_something_no_longer_set_aside_for_is_ignored(self):
        """A suggestion can outlive the thing it was about."""
        stale = TrialPause(name="Gone", from_year=_YEAR, from_month=_OCTOBER)
        assert paused_months(_months(), (_reserve(),), (stale,)) == _months()

    def test_a_pause_starting_beyond_the_window_changes_nothing(self):
        later = TrialPause(name="Christmas", from_year=_YEAR + 5, from_month=1)
        assert paused_months(_months(), (_reserve(),), (later,)) == _months()

    def test_the_months_before_the_pause_are_untouched(self):
        tried = paused_months(
            _months(),
            (_reserve(),),
            (TrialPause(name="Christmas", from_year=_YEAR, from_month=_NOVEMBER),),
        )
        assert tried[0] == _month(_OCTOBER)
        assert tried[1] != _month(_NOVEMBER)


class TestOnlyTheHoldBackChanges:
    """Pausing frees what a day was keeping; it does not add to the account."""

    def _tried(self):
        return paused_months(
            _months(),
            (_reserve(),),
            (TrialPause(name="Christmas", from_year=_YEAR, from_month=_OCTOBER),),
        )

    def test_no_item_moves_and_no_item_changes_amount(self):
        """The balance walks exactly as it did; only the floor under it drops."""
        for original, paused in zip(_months(), self._tried()):
            assert paused.items == original.items

    def test_the_hold_back_falls_by_exactly_the_commitment_s_own_share(self):
        reserve = _reserve()
        for index, (original, paused) in enumerate(zip(_months(), self._tried())):
            freed = [
                was - now
                for was, now in zip(original.reserve_by_day, paused.reserve_by_day)
            ]
            assert freed == list(reserve.by_day[index])

    def test_a_month_holding_nothing_back_is_returned_untouched(self):
        """Nothing to free, so the month is passed through as it came."""
        plain = _months(reserved=False)
        assert (
            paused_months(
                plain,
                (_reserve(),),
                (TrialPause(name="Christmas", from_year=_YEAR, from_month=_OCTOBER),),
            )
            == plain
        )
