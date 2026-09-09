"""Tests for the exported SVG charts.

The export cannot screenshot the QPainter widget, so it redraws the series as
SVG. What matters is that the redraw obeys the same rules the widget does,
because a report that disagreed with the screen would be worse than no report
at all: bars in bar mode, a curve only in bar mode, a zero line only when the
range crosses zero and every value inside the plotting area.
"""

import re

import pytest

from clear_budget.application.reporting._chart_svg_theme import (
    FLOOR_DASH,
    HEIGHT,
    LEGEND_CHAR_WIDTH,
    LEGEND_HEIGHT,
    LEGEND_SWATCH,
    MARGIN_LEFT_MIN,
    MARGIN_RIGHT,
    SOLO_BAR_UNDER,
    WIDTH,
    ZERO_LINE,
)
from clear_budget.application.reporting.chart_svg import chart_svg


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
    assert _grid_left(_svg([_RISING], "line")) == MARGIN_LEFT_MIN


def test_the_left_margin_widens_to_fit_a_large_balance():
    """A label wider than the floor grows the margin instead of truncating."""
    huge = _Series("Bank balance", [999_999_999_900] * _DAYS)
    assert _grid_left(_svg([huge], "line")) > MARGIN_LEFT_MIN


def test_a_label_with_markup_in_it_is_escaped():
    """Card names are user text and must not be able to inject markup."""
    hostile = _Series('<script>"x"</script>', [10] * _DAYS)
    svg = _svg([hostile], "bar")
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg


# ---- the reserve floor ------------------------------------------------------
# A day can be in credit and still not be free, because the month's own
# commitments have already claimed part of the balance. The export has to say
# so with the same four states the widget uses, else the report and the screen
# disagree about the same month.

_FLOOR_PENCE = 130_00


def _floor_svg(series, *, floor_values, mode="bar"):
    return chart_svg(series, mode=mode, labels=_LABELS, floor_values=floor_values)


def _floor_line_count(svg):
    """How many floor polylines the markup carries.

    Matched on the floor's own dash rather than on `<polyline`, because the
    line rendering draws the series that way too.
    """
    return svg.count(f'stroke-dasharray="{FLOOR_DASH}"')


def test_a_day_in_credit_but_under_its_floor_is_dimmed():
    """In credit, so nothing bounced; spoken for, so it is not money to spend."""
    svg = _floor_svg([_RISING], floor_values=[_FLOOR_PENCE] * _DAYS)
    under = sum(1 for v in _RISING.values if 0 <= v < _FLOOR_PENCE)
    assert under > 0
    assert under < _DAYS  # the rest clear the floor, so the test can tell them apart
    assert svg.count(f'fill="{SOLO_BAR_UNDER}"') == under


def test_without_a_floor_no_day_is_dimmed():
    """The reading every export carried before reserves existed."""
    assert f'fill="{SOLO_BAR_UNDER}"' not in _svg([_RISING], "bar")


def test_the_floor_is_drawn_across_the_month():
    svg = _floor_svg([_RISING], floor_values=[_FLOOR_PENCE] * _DAYS)
    assert _floor_line_count(svg) == 1


def test_no_floor_line_is_drawn_when_none_was_given():
    assert _floor_line_count(_svg([_RISING], "bar")) == 0


def test_a_floor_of_one_day_draws_no_line():
    """A line needs two points; one day's floor is a dot nobody can read."""
    svg = _floor_svg([_RISING], floor_values=[_FLOOR_PENCE])
    assert _floor_line_count(svg) == 0
    # The one day it does cover still reads against it.
    assert f'fill="{SOLO_BAR_UNDER}"' in svg


# ---- the legend fits inside the picture -----------------------------------
# It used to step a fixed distance per entry, so four cards plus the total
# curve wrote the last label off the right edge of the canvas and the export
# lost it exactly as the window did.
_TEXT = re.compile(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*>([^<]*)</text>')
_ELLIPSIS = "…"


def _legend_texts(svg: str, wanted) -> list[tuple[float, float, str]]:
    """(x, y, label) for every legend entry in `svg`."""
    return [
        (float(x), float(y), text)
        for x, y, text in _TEXT.findall(svg)
        if any(text.startswith(prefix) for prefix in wanted)
    ]


def _cards(count: int) -> list[_Series]:
    return [_Series(f"Card number {index}", [100_00] * _DAYS) for index in range(count)]


def test_every_legend_label_ends_inside_the_canvas():
    """Four cards plus the total curve: the case that ran off the edge."""
    cards = _cards(4)
    svg = _svg(cards, "bar")
    entries = _legend_texts(svg, ("Card number", "Curve"))
    assert len(entries) == len(cards) + 1
    for x, _y, label in entries:
        assert x + len(label) * LEGEND_CHAR_WIDTH <= WIDTH - MARGIN_RIGHT


def test_a_legend_too_wide_for_one_row_wraps_onto_the_next():
    svg = _svg(_cards(12), "bar")
    rows = {y for _x, y, _label in _legend_texts(svg, ("Card number", "Curve"))}
    assert len(rows) > 1
    assert sorted(rows) == [min(rows) + LEGEND_HEIGHT * i for i in range(len(rows))]


def test_a_wrapped_legend_pushes_the_plot_down_rather_than_over_it():
    """The band grows by a row, so no bar is drawn under a legend label."""
    svg = _svg(_cards(12), "bar")
    lowest_label = max(y for _x, y, _label in _legend_texts(svg, ("Card number",)))
    assert lowest_label > max(
        y for _x, y, _label in _legend_texts(_svg(_cards(2), "bar"), ("Card number",))
    )
    bars = [
        (float(y), float(height))
        for y, height in re.findall(
            r'<rect x="[\d.]+" y="([\d.]+)" width="[\d.]+" height="([\d.]+)"', svg
        )
        if float(height) != LEGEND_SWATCH
    ]
    assert bars
    assert min(top for top, _height in bars) >= lowest_label


def test_a_label_wider_than_a_whole_row_is_shortened():
    """No wrap can save it, so it is cut rather than drawn over the edge."""
    svg = _svg([_Series("N" * 400, [100_00] * _DAYS)], "bar")
    (x, _y, label), *_rest = _legend_texts(svg, ("N",))
    assert label.endswith(_ELLIPSIS)
    assert x + len(label) * LEGEND_CHAR_WIDTH <= WIDTH - MARGIN_RIGHT
