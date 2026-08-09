"""Tests for the exported SVG charts.

The export cannot screenshot the QPainter widget, so it redraws the series as
SVG. What matters is that the redraw obeys the same rules the widget does,
because a report that disagreed with the screen would be worse than no report
at all: bars in bar mode, a curve only in bar mode, a zero line only when the
range crosses zero and every value inside the plotting area.
"""

import re

import pytest

from clear_budget.application.reporting.chart_svg import (
    HEIGHT,
    WIDTH,
    ZERO_LINE,
    _MARGIN_LEFT_MIN,
    chart_svg,
)


class _Series:
    def __init__(self, label, values):
        self.label = label
        self.values = tuple(values)


_DAYS = 10
_LABELS = tuple((day, str(day)) for day in (1, 5, _DAYS))
_RISING = _Series("Bank balance", [100_00 + 10_00 * d for d in range(_DAYS)])
_CROSSES_ZERO = _Series("Bank balance", [50_00 - 15_00 * d for d in range(_DAYS)])


def _svg(series, mode):
    return chart_svg(series, mode=mode, labels=_LABELS)


# One rect is the chart's own dark background, so it reads correctly wherever
# it is embedded; the rest are bars and legend swatches.
_CANVAS_RECTS = 1


def test_bar_mode_draws_one_rectangle_per_day():
    """Plus two legend swatches: the series and the curve."""
    svg = _svg([_RISING], "bar")
    assert svg.count("<rect") == _DAYS + 2 + _CANVAS_RECTS


def test_below_zero_days_fill_in_the_zero_lines_red():
    """An overdrawn day's bar wears the danger colour, not the series one.

    The zero line itself is a stroke, never a fill, so every danger FILL in
    the markup is a bar.
    """
    svg = _svg([_CROSSES_ZERO], "bar")
    negative_days = sum(1 for v in _CROSSES_ZERO.values if v < 0)
    assert negative_days > 0
    assert svg.count(f'fill="{ZERO_LINE}"') == negative_days


def test_line_mode_draws_a_polyline_and_no_bars():
    svg = _svg([_RISING], "line")
    assert "<polyline" in svg
    assert svg.count("<rect") == 1 + _CANVAS_RECTS  # legend swatch only


def test_only_bar_mode_carries_the_curve():
    """Matches the widget: the line already passes through every value."""
    assert "<path" in _svg([_RISING], "bar")
    assert "<path" not in _svg([_RISING], "line")


def test_the_curve_is_named_in_the_legend_only_when_drawn():
    assert "Curve" in _svg([_RISING], "bar")
    assert "Curve" not in _svg([_RISING], "line")


def test_two_series_label_the_curve_as_a_total():
    other = _Series("Card", [20_00] * _DAYS)
    assert "Curve (total)" in _svg([_RISING, other], "bar")


def test_the_zero_line_appears_only_when_the_range_crosses_zero():
    assert "stroke-dasharray" in _svg([_CROSSES_ZERO], "line")
    assert "stroke-dasharray" not in _svg([_RISING], "line")


def test_the_series_label_reaches_the_legend():
    assert "Bank balance" in _svg([_RISING], "bar")


def test_a_flat_month_still_renders():
    """A zero-height value range must not divide by zero."""
    flat = _Series("Bank balance", [1000] * _DAYS)
    assert "<svg" in _svg([flat], "bar")


def test_an_all_zero_month_still_renders():
    """Low and high both land on zero, the one case with no range at all."""
    empty = _Series("Bank balance", [0] * _DAYS)
    assert "<svg" in _svg([empty], "bar")


def test_a_single_day_still_renders():
    """One point has no segment to interpolate, so the curve is skipped."""
    one = _Series("Bank balance", [1000])
    svg = chart_svg([one], mode="bar", labels=((1, "1"),))
    assert "<svg" in svg
    assert "<path" not in svg


@pytest.mark.parametrize("mode", ["bar", "line"])
def test_everything_drawn_stays_inside_the_canvas(mode):
    """A value escaping the viewBox would be clipped in the browser."""
    svg = _svg([_CROSSES_ZERO], mode)
    for x, y in re.findall(r'(?:x|x1|x2)="(-?[\d.]+)" (?:y|y1|y2)="(-?[\d.]+)"', svg):
        assert 0 <= float(x) <= WIDTH
        assert 0 <= float(y) <= HEIGHT


def _grid_left(svg):
    """The x the grid lines start at, which is the measured left margin."""
    return float(re.search(r'<line x1="(\d+)"', svg).group(1))


def test_the_left_margin_keeps_its_floor_for_short_labels():
    """Ordinary balances leave the margin at its minimum."""
    assert _grid_left(_svg([_RISING], "line")) == _MARGIN_LEFT_MIN


def test_the_left_margin_widens_to_fit_a_large_balance():
    """A label wider than the floor grows the margin instead of truncating."""
    huge = _Series("Bank balance", [999_999_999_900] * _DAYS)
    assert _grid_left(_svg([huge], "line")) > _MARGIN_LEFT_MIN


def test_a_label_with_markup_in_it_is_escaped():
    """Card names are user text and must not be able to inject markup."""
    hostile = _Series('<script>"x"</script>', [10] * _DAYS)
    svg = _svg([hostile], "bar")
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg
