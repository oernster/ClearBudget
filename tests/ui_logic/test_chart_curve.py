"""Qt-free tests for the month graph's following curve.

The maths lives in the UI layer but is pure Python, so it is tested here
without a QApplication (the same arrangement as test_solvency_colours).

What the curve promises, and why:
  * it FOLLOWS the data, passing through every day's real value, rather than
    averaging across days. An averaged line cut through a tall day, which drew
    a balance the account never had;
  * it never overshoots. A curve that bulged above a peak or below a trough
    would show the same lie in the other direction;
  * one curve covers every plotted series, so it is the day-end total.
"""

from itertools import pairwise

from clear_budget.ui.widgets._chart_curve import (
    bezier_segments,
    daily_totals,
    inflection_days,
    monotone_slopes,
)

# A quiet month with one tall day in the middle: the shape that showed the
# averaged line was wrong.
_SPIKE = (100, 100, 100, 900, 100, 100, 100)


def _sample(points, steps: int = 24):
    """Every (x, y) the drawn curve actually passes through, densely sampled."""
    sampled = []
    start = points[0]
    for control_1, control_2, end in bezier_segments(points):
        for step in range(steps + 1):
            t = step / steps
            inverse = 1 - t
            x = (
                inverse**3 * start[0]
                + 3 * inverse**2 * t * control_1[0]
                + 3 * inverse * t**2 * control_2[0]
                + t**3 * end[0]
            )
            y = (
                inverse**3 * start[1]
                + 3 * inverse**2 * t * control_1[1]
                + 3 * inverse * t**2 * control_2[1]
                + t**3 * end[1]
            )
            sampled.append((x, y))
        start = end
    return sampled


def _as_points(values):
    return [(float(i), float(v)) for i, v in enumerate(values)]


# ---------------------------------------------------------------------------
# The curve follows the data.
# ---------------------------------------------------------------------------


def test_every_segment_ends_on_the_next_data_point() -> None:
    """The curve is an interpolation, so each point is on it by construction."""
    points = _as_points(_SPIKE)
    ends = [end for _c1, _c2, end in bezier_segments(points)]
    assert ends == points[1:]


def test_the_curve_reaches_the_peak_value() -> None:
    """The tall day is on the curve, not smoothed away beneath it."""
    peak = max(y for _x, y in _sample(_as_points(_SPIKE)))
    assert peak == max(_SPIKE)


def test_the_curve_never_overshoots_a_peak() -> None:
    """Nothing on the curve sits above the highest day."""
    highest = max(y for _x, y in _sample(_as_points(_SPIKE)))
    assert highest <= max(_SPIKE) + 1e-9


def test_the_curve_never_undershoots_a_trough() -> None:
    """Nothing on the curve dips below the lowest day (a dip to zero here)."""
    dip = (500, 500, 500, 0, 500, 500, 500)
    lowest = min(y for _x, y in _sample(_as_points(dip)))
    assert lowest >= min(dip) - 1e-9


def test_a_falling_month_stays_falling() -> None:
    """A balance that only ever falls produces a curve that only ever falls."""
    values = (1000, 900, 700, 400, 100)
    ys = [y for _x, y in _sample(_as_points(values))]
    assert all(later <= earlier + 1e-9 for earlier, later in pairwise(ys))


def test_a_flat_month_gives_a_flat_curve() -> None:
    values = (250,) * 6
    assert {round(y, 6) for _x, y in _sample(_as_points(values))} == {250.0}


# ---------------------------------------------------------------------------
# Tangents.
# ---------------------------------------------------------------------------


def test_a_turning_point_gets_a_flat_tangent() -> None:
    """Flattening the peak is what keeps the curve from sailing past it."""
    slopes = monotone_slopes([0, 1, 2], [0, 10, 0])
    assert slopes[1] == 0.0


def test_a_straight_run_keeps_its_slope() -> None:
    slopes = monotone_slopes([0, 1, 2, 3], [0, 10, 20, 30])
    assert slopes == (10.0, 10.0, 10.0, 10.0)


def test_slopes_of_a_single_point_are_flat() -> None:
    assert monotone_slopes([0], [5]) == (0.0,)


def test_segments_need_two_points() -> None:
    assert bezier_segments([(0.0, 0.0)]) == ()
    assert bezier_segments([]) == ()


# ---------------------------------------------------------------------------
# One curve covers every series.
# ---------------------------------------------------------------------------


def test_daily_totals_sums_every_series_for_each_day() -> None:
    assert daily_totals([(10, 20, 30), (1, 2, 3)]) == (11, 22, 33)


def test_daily_totals_of_a_single_series_is_that_series() -> None:
    """With one series the curve traces its own bars, not an aggregate."""
    assert daily_totals([(5, 6, 7)]) == (5, 6, 7)


def test_daily_totals_of_nothing_is_empty() -> None:
    assert daily_totals([]) == ()


def test_daily_totals_truncates_to_the_shortest_series() -> None:
    """A ragged input must not raise; it stops at the shortest series."""
    assert daily_totals([(1, 2, 3), (10, 20)]) == (11, 22)


# ---------------------------------------------------------------------------
# Inflection days (what the hover readout aims at).
# ---------------------------------------------------------------------------


def test_inflection_days_finds_a_peak() -> None:
    assert inflection_days((1, 2, 9, 2, 1)) == (3,)


def test_inflection_days_finds_a_trough() -> None:
    assert inflection_days((9, 5, 1, 5, 9)) == (3,)


def test_inflection_days_finds_several() -> None:
    assert inflection_days((0, 5, 0, 5, 0)) == (2, 3, 4)


def test_a_run_that_only_falls_has_no_inflection() -> None:
    assert inflection_days((100, 80, 60, 40)) == ()


def test_a_plateau_does_not_report_every_day_inside_it() -> None:
    assert inflection_days((0, 5, 5, 5, 9)) == ()


def test_inflection_days_ignores_the_endpoints() -> None:
    assert inflection_days((5, 1)) == ()
    assert inflection_days(()) == ()
