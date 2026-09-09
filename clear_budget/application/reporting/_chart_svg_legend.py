"""The exported chart's legend: laid out to fit, wrapped when it will not.

The legend used to step a fixed 190 units per entry from the axis margin.
Four cards plus the total curve is five of those steps, which is wider than
the canvas, so the last label was written off the right edge of the picture
and the HTML export lost it exactly as the window did.

There are no font metrics in a string build, so a label's width is estimated
from its character count at an upper bound for the face (the same device the
y-axis margin uses). Each entry then takes the room its own words need, a row
wraps when the next entry would cross the right margin and a label too wide
for a whole row on its own is shortened rather than drawn over the edge.
"""

from __future__ import annotations

from math import ceil

from clear_budget.application.reporting import _chart_svg_theme as theme
from clear_budget.application.reporting._chart_svg_text import axis_text

_CURVE_LABEL = "Curve"
_CURVE_TOTAL_LABEL = "Curve (total)"
_ELLIPSIS = "…"


def _entries(plot) -> list[tuple]:
    """(colour, label) for every series, plus the curve when it is drawn.

    The swatch has to be the colour actually drawn, which for one series
    differs between the two renderings: green bars, a deep blue line.
    """
    mark = plot.bar_colour if plot.with_curve else plot.line_colour
    entries = [(mark(i), s.label) for i, s in enumerate(plot.series)]
    if plot.with_curve:
        label = _CURVE_TOTAL_LABEL if len(plot.series) > 1 else _CURVE_LABEL
        entries.append((plot.curve_colour(), label))
    return entries


def _text_width(label) -> int:
    """An upper bound on how wide `label` will render, in user units."""
    return ceil(len(str(label)) * theme.LEGEND_CHAR_WIDTH)


def _shortened(label: str, room: int) -> str:
    """`label` cut to fit `room`, ending in an ellipsis."""
    keep = max(1, int(room / theme.LEGEND_CHAR_WIDTH) - len(_ELLIPSIS))
    return label[:keep] + _ELLIPSIS


def rows(plot) -> list[list[tuple]]:
    """The legend entries grouped into rows that fit inside the canvas.

    Each entry is (colour, label, x), placed left to right from the axis
    margin; a new row starts as soon as one would cross the right margin.
    """
    limit = theme.WIDTH - theme.MARGIN_RIGHT
    step = theme.LEGEND_SWATCH + theme.LEGEND_TEXT_GAP
    room = max(1, limit - plot.left - step)
    laid_out: list[list[tuple]] = [[]]
    x = plot.left
    for colour, label in _entries(plot):
        text = str(label)
        width = _text_width(text)
        if width > room:
            text = _shortened(text, room)
            width = _text_width(text)
        if laid_out[-1] and x + step + width > limit:
            laid_out.append([])
            x = plot.left
        laid_out[-1].append((colour, text, x))
        x += step + width + theme.LEGEND_ENTRY_GAP
    return laid_out


def legend(plot) -> list[str]:
    """The legend's markup, one swatch and one label per entry."""
    parts = []
    for row_index, row in enumerate(plot.legend_rows):
        y = theme.MARGIN_TOP + row_index * theme.LEGEND_HEIGHT
        for colour, label, x in row:
            parts.append(
                f'<rect x="{x}" y="{y}" width="{theme.LEGEND_SWATCH}" '
                f'height="{theme.LEGEND_SWATCH}" fill="{colour}"/>'
            )
            parts.append(
                axis_text(
                    x + theme.LEGEND_SWATCH + theme.LEGEND_TEXT_GAP,
                    y + theme.LEGEND_TEXT_BASELINE,
                    "start",
                    label,
                )
            )
    return parts
