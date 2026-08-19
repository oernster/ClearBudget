"""The sustainable-spend calculation.

The figure answers "what can I spend today", so it is bounded by the last
month that still clears the floor with nothing spent at all. A month already
under the floor is a shortfall rather than a spending limit: letting it drive
the figure reported nothing spendable while the months in front of it still
had real headroom, which answered "does my budget hold" in the slot reserved
for the other question.

The shortfall is not discarded, which is what made the older truncating
version dishonest. It is carried on the result so a caller must decide what to
say about it; the tests below pin both halves.
"""

from datetime import date, timedelta

import pytest

from clear_budget.domain.services.safe_to_spend import (
    DayProjection,
    SustainableError,
    sustainable_capacity,
    sustainable_spend,
)

_TODAY = date(2026, 8, 19)


def _run(balances: dict[date, int], **kwargs):
    projection = [DayProjection(day=d, balance_pence=p) for d, p in balances.items()]
    return sustainable_spend(projection=projection, today=_TODAY, **kwargs)


def _month(year: int, month: int, days: int, balance: int) -> dict[date, int]:
    return {date(year, month, d): balance for d in range(1, days + 1)}


def _august(balance: int, *, from_day: int = 19) -> dict[date, int]:
    return {date(2026, 8, d): balance for d in range(from_day, 32)}


class TestTheWindowIsBoundedByWholeMonths:
    def test_a_one_month_window_stops_at_the_end_of_this_month(self):
        balances = _august(50000) | _month(2026, 9, 30, -90000)
        result = _run(balances, window_months=1)
        assert result.covered_end == date(2026, 8, 31)
        assert result.amount_pence == 50000

    def test_a_healthy_second_month_extends_what_the_figure_covers(self):
        balances = _august(50000) | _month(2026, 9, 30, 40000)
        result = _run(balances, window_months=2)
        assert result.covered_end == date(2026, 9, 30)
        assert result.amount_pence == 40000

    def test_a_window_longer_than_the_projection_uses_what_there_is(self):
        result = _run(_august(50000), window_months=12)
        assert result.covered_end == date(2026, 8, 31)


class TestAMonthThatCannotBeSavedDoesNotSetTheFigure:
    """The rule this calculation was rewritten for.

    A month under the floor with nothing spent stays under it however little
    is spent. Reporting nothing spendable on its account describes a
    structural shortfall as though it were a limit on today.
    """

    def test_the_figure_stops_at_the_last_month_that_stands_alone(self):
        balances = _august(50000) | _month(2026, 9, 30, -20000)
        result = _run(balances, window_months=2)
        assert result.amount_pence == 50000
        assert result.covered_end == date(2026, 8, 31)
        assert result.binding_day.month == 8

    def test_the_unsaveable_month_is_reported_rather_than_dropped(self):
        balances = _august(50000) | _month(2026, 9, 30, -20000)
        result = _run(balances, window_months=2)
        assert result.has_shortfall
        assert result.shortfall_pence == 20000
        assert result.shortfall_day.month == 9

    def test_the_shortfall_is_measured_against_the_floor(self):
        balances = _august(
            50000,
        ) | _month(2026, 9, 30, -20000)
        result = _run(balances, window_months=2, floor_pence=1000)
        assert result.amount_pence == 49000
        assert result.shortfall_pence == 21000

    def test_a_healthy_month_after_a_collapse_is_still_not_promised(self):
        """A month after a collapse is projected FROM that collapse."""
        balances = (
            _august(50000) | _month(2026, 9, 30, -20000) | _month(2026, 10, 31, 90000)
        )
        result = _run(balances, window_months=3)
        assert result.covered_end == date(2026, 8, 31)
        assert result.amount_pence == 50000

    def test_a_window_that_stands_throughout_reports_no_shortfall(self):
        balances = _august(50000) | _month(2026, 9, 30, 40000)
        result = _run(balances, window_months=2)
        assert not result.has_shortfall
        assert result.shortfall_pence == 0
        assert result.shortfall_day is None

    def test_this_month_being_under_leaves_nothing_to_promise(self):
        """Only then is the headline the sum to find."""
        balances = _august(-20000) | _month(2026, 9, 30, -90000)
        result = _run(balances, window_months=2)
        assert result.amount_pence == -20000
        assert result.binding_day.month == 8

    def test_the_deepest_day_sets_the_figure_not_the_first_bad_one(self):
        balances = _august(50000)
        balances[date(2026, 8, 25)] = -1000
        balances[date(2026, 8, 28)] = -7000
        result = _run(balances, window_months=1)
        assert result.amount_pence == -7000
        assert result.binding_day == date(2026, 8, 28)

    def test_a_surviving_window_reports_what_it_can_spare(self):
        result = _run(_august(50000), window_months=1)
        assert result.is_sustainable
        assert result.amount_pence == 50000


class TestTheFloor:
    def test_the_floor_comes_off_the_top(self):
        result = _run(_august(50000), floor_pence=2000, window_months=1)
        assert result.amount_pence == 48000
        assert result.floor_pence == 2000

    def test_a_balance_above_zero_but_under_the_floor_is_a_shortfall(self):
        result = _run(_august(500), floor_pence=2000, window_months=1)
        assert not result.is_sustainable
        assert result.amount_pence == -1500


class TestRejectedInputs:
    def test_a_negative_floor_is_refused(self):
        with pytest.raises(SustainableError, match="floor"):
            _run(_august(50000), floor_pence=-1)

    def test_a_window_shorter_than_a_month_is_refused(self):
        with pytest.raises(SustainableError, match="at least one month"):
            _run(_august(50000), window_months=0)

    def test_a_projection_that_omits_today_is_refused(self):
        with pytest.raises(SustainableError, match="include today"):
            _run(_august(50000, from_day=20))

    def test_an_empty_projection_is_refused(self):
        with pytest.raises(SustainableError, match="include today"):
            _run({})


class TestSustainableCapacity:
    def _steps(self, balances, **kwargs):
        projection = [
            DayProjection(day=d, balance_pence=p) for d, p in balances.items()
        ]
        return sustainable_capacity(projection=projection, today=_TODAY, **kwargs)

    def test_the_first_step_equals_the_headline(self):
        balances = _august(50000)
        balances[date(2026, 8, 20)] = 10000
        steps = self._steps(balances, window_months=1)
        headline = _run(balances, window_months=1)
        assert steps[0].from_day == _TODAY
        assert steps[0].amount_pence == headline.amount_pence

    def test_waiting_past_the_low_day_raises_the_figure(self):
        balances = _august(50000)
        balances[date(2026, 8, 20)] = 10000
        steps = self._steps(balances, window_months=1)
        assert steps[-1].amount_pence > steps[0].amount_pence
        assert steps[-1].from_day > date(2026, 8, 20)

    def test_a_flat_window_reports_one_step(self):
        assert len(self._steps(_august(50000), window_months=1)) == 1

    def test_steps_never_leave_this_month(self):
        balances = _august(50000) | _month(2026, 9, 30, 90000)
        steps = self._steps(balances, window_months=2)
        assert all(s.from_day.month == 8 for s in steps)

    def test_a_later_month_caps_every_step(self):
        # Waiting cannot buy past what the months it covers will bear.
        balances = _august(50000) | _month(2026, 9, 30, 1000)
        steps = self._steps(balances, window_months=2)
        assert all(s.amount_pence == 1000 for s in steps)
        assert all(s.binding_day.month == 9 for s in steps)

    def test_a_month_that_cannot_be_saved_caps_nothing(self):
        # The schedule is measured over the same stretch the headline
        # promises, so an unsaveable month cannot flatten every row to zero.
        balances = _august(50000) | _month(2026, 9, 30, -20000)
        balances[date(2026, 8, 20)] = 10000
        steps = self._steps(balances, window_months=2)
        assert steps[0].amount_pence == 10000
        assert steps[-1].amount_pence == 50000
        assert all(s.binding_day.month == 8 for s in steps)

    def test_a_negative_floor_is_refused(self):
        with pytest.raises(SustainableError, match="floor"):
            self._steps(_august(50000), floor_pence=-1)


def test_the_window_counts_calendar_months_not_thirty_day_blocks():
    """A longer window can only ever see further, never promise further."""
    balances = _august(50000) | _month(2026, 9, 30, 40000) | _month(2026, 10, 31, -5000)
    result = _run(balances, window_months=2)
    assert result.covered_end == date(2026, 9, 30)
    assert result.amount_pence == 40000
    assert not result.has_shortfall
    later = _run(balances, window_months=3)
    # October cannot be saved, so it is named rather than allowed to set the
    # figure. The promise still stops where September ends.
    assert later.covered_end == date(2026, 9, 30)
    assert later.amount_pence == 40000
    assert later.shortfall_pence == 5000
    assert later.shortfall_day.month == 10
    assert later.covered_end - result.covered_end == timedelta(days=0)
