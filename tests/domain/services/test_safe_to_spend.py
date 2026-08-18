"""The sustainable-spend calculation, over a bounded window with no truncation."""

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
        assert result.window_end == date(2026, 8, 31)
        assert result.amount_pence == 50000

    def test_a_two_month_window_lets_next_month_veto(self):
        balances = _august(50000) | _month(2026, 9, 30, -90000)
        result = _run(balances, window_months=2)
        assert result.window_end == date(2026, 9, 30)
        assert result.amount_pence == -90000

    def test_a_window_longer_than_the_projection_uses_what_there_is(self):
        result = _run(_august(50000), window_months=12)
        assert result.window_end == date(2026, 8, 31)


class TestNoDayIsExcluded:
    def test_a_month_already_under_the_floor_still_vetoes_the_figure(self):
        # The whole point. The old calculation stopped at the first day below
        # the floor and reported the healthy stretch before it, which funded
        # its own deficit: spending that figure deepened the excluded days by
        # exactly the amount spent.
        balances = _august(50000) | _month(2026, 9, 30, -20000)
        result = _run(balances, window_months=2)
        assert result.amount_pence == -20000
        assert result.binding_day.month == 9

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
        # Waiting cannot buy past what the window will bear.
        balances = _august(50000) | _month(2026, 9, 30, 1000)
        steps = self._steps(balances, window_months=2)
        assert all(s.amount_pence == 1000 for s in steps)
        assert all(s.binding_day.month == 9 for s in steps)

    def test_a_negative_floor_is_refused(self):
        with pytest.raises(SustainableError, match="floor"):
            self._steps(_august(50000), floor_pence=-1)


def test_the_window_counts_calendar_months_not_thirty_day_blocks():
    balances = _august(50000) | _month(2026, 9, 30, 40000) | _month(2026, 10, 31, -5000)
    result = _run(balances, window_months=2)
    assert result.window_end == date(2026, 9, 30)
    assert result.amount_pence == 40000
    later = _run(balances, window_months=3)
    assert later.window_end == date(2026, 10, 31)
    assert later.amount_pence == -5000
    assert later.window_end - result.window_end == timedelta(days=31)
