"""Qt-free tests for the month graph's trend and inflection maths.

The maths lives in the UI layer but is pure Python, so it is tested here
without a QApplication (the same arrangement as test_solvency_colours).

What the graph promises:
  * one trend curve covers every plotted series, so it is the smoothed TOTAL;
  * the curve spans the whole month, so the ends are averaged over the days
    that exist rather than dropped;
  * an inflection day is a genuine change of direction, so a run that only
    ever falls reports none and a plateau does not report every day in it.
"""

from clear_budget.ui.widgets._chart_trend import (
    TREND_WINDOW_DAYS,
    daily_totals,
    inflection_days,
    moving_average,
    trend_values,
)


def test_daily_totals_sums_every_series_for_each_day() -> None:
    assert daily_totals([(10, 20, 30), (1, 2, 3)]) == (11, 22, 33)


def test_daily_totals_of_a_single_series_is_that_series() -> None:
    assert daily_totals([(5, 6, 7)]) == (5, 6, 7)


def test_daily_totals_of_nothing_is_empty() -> None:
    assert daily_totals([]) == ()


def test_daily_totals_truncates_to_the_shortest_series() -> None:
    """A ragged input must not raise; it stops at the shortest series."""
    assert daily_totals([(1, 2, 3), (10, 20)]) == (11, 22)


def test_moving_average_of_a_flat_run_is_that_value() -> None:
    assert moving_average((100,) * 7) == (100,) * 7


def test_moving_average_smooths_a_single_spike() -> None:
    """A one-day spike is spread across the window, not preserved."""
    smoothed = moving_average((0, 0, 500, 0, 0), window=5)
    assert smoothed[2] == 100
    assert max(smoothed) < 500


def test_moving_average_spans_the_whole_input() -> None:
    """Every day gets a value, so the curve reaches both ends."""
    values = tuple(range(10))
    assert len(moving_average(values)) == len(values)


def test_moving_average_clamps_at_the_ends() -> None:
    """The first point averages only the days that exist (itself plus two)."""
    assert moving_average((0, 3, 6, 9, 12), window=5)[0] == round((0 + 3 + 6) / 3)


def test_moving_average_of_nothing_is_empty() -> None:
    assert moving_average(()) == ()


def test_moving_average_follows_a_rising_run() -> None:
    smoothed = moving_average(tuple(range(0, 1000, 100)))
    assert smoothed == tuple(sorted(smoothed))


def test_trend_values_smooths_the_total_of_all_series() -> None:
    flat = trend_values([(100,) * 6, (200,) * 6])
    assert flat == (300,) * 6


def test_trend_window_is_odd_so_the_average_is_centred() -> None:
    assert TREND_WINDOW_DAYS % 2 == 1


def test_inflection_days_finds_a_peak() -> None:
    """Up then down on day 3 (1-based) is a peak."""
    assert inflection_days((1, 2, 9, 2, 1)) == (3,)


def test_inflection_days_finds_a_trough() -> None:
    assert inflection_days((9, 5, 1, 5, 9)) == (3,)


def test_inflection_days_finds_several() -> None:
    assert inflection_days((0, 5, 0, 5, 0)) == (2, 3, 4)


def test_a_run_that_only_falls_has_no_inflection() -> None:
    assert inflection_days((100, 80, 60, 40)) == ()


def test_a_plateau_does_not_report_every_day_inside_it() -> None:
    """Flat steps are skipped, so a shelf is not a direction change."""
    assert inflection_days((0, 5, 5, 5, 9)) == ()


def test_inflection_days_ignores_the_endpoints() -> None:
    """A direction change needs a day either side, so ends never qualify."""
    assert inflection_days((5, 1)) == ()
    assert inflection_days(()) == ()
