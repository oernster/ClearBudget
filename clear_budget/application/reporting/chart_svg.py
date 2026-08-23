"""Bar and line charts as inline SVG. Pure Python, no Qt and no I/O.

The on-screen graph is QPainter, which cannot go into a file anyone can open
in a browser. Rather than screenshot the widget, the export redraws the same
series with the same rules as vector SVG: it stays sharp at any zoom, weighs
almost nothing, needs no image file beside the HTML and (being a pure string
build) is testable without a QApplication.

Fixed dark palette, matching the app's dark theme, rather than following
whichever theme is active. An export that changed appearance depending on
what the toggle happened to be set to would be unpredictable and the app's
own identity is the dark one. It carries its own background rather than
relying on the page, so it reads correctly wherever it is embedded. Printing
one will use ink; that is the accepted cost of matching the app.

The chart rules match the widget exactly (see _line_bar_chart.py): the bar
rendering carries the following curve through every day's real value, the
line rendering plots the days directly and needs none, the axis always
includes zero and the zero line is drawn when the range crosses it.
"""

from __future__ import annotations

from math import ceil

from clear_budget.application.reporting.curve import bezier_segments, daily_totals

# The app's dark palette, mirrored here because the application layer may not
# import ui.theme_tokens. Values match DARK / SERIES_DARK / CURVE_DARK.
PANEL = "#242938"
MUTED = "#9ca3af"
GRID = "#3a4156"
ZERO_LINE = "#f87171"
CURVE = "#e879f9"
SERIES = ("#60a5fa", "#34d399", "#fbbf24", "#c084fc", "#22d3ee", "#fb923c")

# Role colours for a chart plotting a SINGLE series, mirroring
# CHART_LINE_DARK / CHART_BAR_DARK / SOLO_CURVE_DARK in ui.theme_tokens. With
# one series nothing needs telling apart, so the mark says what it IS: a deep
# blue line for the running balance, green bars for the individual days. The
# line stays neutral because it spans positive and negative days alike; a bar
# is one day, so green states a fact about a day that really is in credit. A
# below-zero bar still fills in ZERO_LINE's red.
SOLO_LINE = "#0ea5e9"
SOLO_BAR = "#34d399"
SOLO_CURVE = SOLO_LINE
# A day below zero but inside an ARRANGED overdraft, mirroring
# CHART_BAR_WITHIN_DARK. The facility is there to absorb that day, so red
# would say a payment bounced when none did; red stays for a day past the
# agreed floor. With no facility the floor is zero and this never appears.
SOLO_BAR_WITHIN = "#f59e0b"

WIDTH = 880
HEIGHT = 380
# The left margin grows to fit the widest y-axis label, mirroring the
# on-screen chart's measured margin, so a large balance never truncates.
# SVG has no font metrics at build time, so the width is estimated from the
# label's character count: a digit in a 12px sans face is a touch over 7px
# wide and the estimate rounds up so a label never overruns its estimate.
_MARGIN_LEFT_MIN = 96
_AXIS_CHAR_WIDTH = 7.2
_AXIS_LABEL_GAP = 8
_AXIS_LABEL_INSET = 4
_MARGIN_RIGHT = 20
_MARGIN_TOP = 16
_MARGIN_BOTTOM = 40
_LEGEND_HEIGHT = 26

_GRID_LINES = 4
_BAR_SLOT_FILL = 0.8
_RANGE_PAD_FRACTION = 0.05
_CURVE_WIDTH = 3
_LINE_WIDTH = 2
_LEGEND_SWATCH = 12
_LEGEND_GAP = 190
_AXIS_FONT = 12


def _escape(text: str) -> str:
    """Escape the five characters that would otherwise break the markup."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _money(pence: int) -> str:
    """Format pence as pounds for an axis label, without a currency symbol."""
    return f"{pence / 100:,.0f}"


class _Plot:
    """The plotting area and the value-to-pixel mapping for one chart."""

    def __init__(self, series, *, with_curve: bool, floor_pence: int = 0) -> None:
        self.series = list(series)
        # How far below zero a bar may sit before it reads as red. Zero (no
        # arranged overdraft) means every below-zero bar is red, as before.
        self.floor_pence = -abs(int(floor_pence))
        self.days = len(self.series[0].values)
        self.totals = daily_totals([s.values for s in self.series])
        self.with_curve = with_curve
        values = [v for s in self.series for v in s.values]
        if with_curve:
            values += list(self.totals)
        low = min(0, min(values))
        high = max(0, max(values))
        if low == high:
            high = low + 1
        pad = max(1, int((high - low) * _RANGE_PAD_FRACTION))
        self.low = low - pad if low < 0 else low
        self.high = high + pad
        # The tick labels, top to bottom; the margin is sized to the widest.
        self.y_labels = tuple(
            _money(round(self.high - (self.high - self.low) * i / _GRID_LINES))
            for i in range(_GRID_LINES + 1)
        )
        widest = max(len(label) for label in self.y_labels)
        estimated = (
            ceil(widest * _AXIS_CHAR_WIDTH) + _AXIS_LABEL_GAP + _AXIS_LABEL_INSET
        )
        self.left = max(_MARGIN_LEFT_MIN, estimated)
        self.top = _MARGIN_TOP + _LEGEND_HEIGHT
        self.width = WIDTH - self.left - _MARGIN_RIGHT
        self.height = HEIGHT - self.top - _MARGIN_BOTTOM

    def y_at(self, pence: float) -> float:
        return self.top + self.height * (self.high - pence) / (self.high - self.low)

    def x_at(self, day: int) -> float:
        return self.left + self.width * (day - 1) / max(1, self.days - 1)

    def colour(self, index: int) -> str:
        return SERIES[index % len(SERIES)]

    @property
    def solo(self) -> bool:
        """Whether this plot carries exactly one series."""
        return len(self.series) == 1

    def bar_colour(self, index: int) -> str:
        """The fill for a positive bar of series `index`."""
        return SOLO_BAR if self.solo else self.colour(index)

    def day_bar_colour(self, index: int, value: int) -> str:
        """Three-state fill for one day: in credit, inside the overdraft, past it."""
        if value >= 0:
            return self.bar_colour(index)
        return SOLO_BAR_WITHIN if value >= self.floor_pence else ZERO_LINE

    def line_colour(self, index: int) -> str:
        """The stroke for the plotted line of series `index`."""
        return SOLO_LINE if self.solo else self.colour(index)

    def curve_colour(self) -> str:
        """The following curve's stroke.

        The line's blue over a lone series' bars; its own hue when several
        series share the axis, where it must not read as one more of them.
        """
        return SOLO_CURVE if self.solo else CURVE


def _grid(plot: _Plot) -> list[str]:
    parts = []
    # The same labels the margin was estimated from, so they always fit.
    for i, label in enumerate(plot.y_labels):
        fraction = i / _GRID_LINES
        y = plot.top + plot.height * fraction
        parts.append(
            f'<line x1="{plot.left}" y1="{y:.1f}" '
            f'x2="{plot.left + plot.width}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{plot.left - _AXIS_LABEL_GAP}" y="{y + 4:.1f}" '
            f'text-anchor="end" '
            f'fill="{MUTED}" font-size="{_AXIS_FONT}">{_escape(label)}</text>'
        )
    return parts


def _x_labels(plot: _Plot, *, labels) -> list[str]:
    base = plot.top + plot.height + 18
    parts = []
    for day, label in labels:
        parts.append(
            f'<text x="{plot.x_at(day):.1f}" y="{base}" text-anchor="middle" '
            f'fill="{MUTED}" font-size="{_AXIS_FONT}">{_escape(label)}</text>'
        )
    return parts


def _zero_line(plot: _Plot) -> list[str]:
    if not plot.low < 0 < plot.high:
        return []
    y = plot.y_at(0)
    return [
        (
            f'<line x1="{plot.left}" y1="{y:.1f}" '
            f'x2="{plot.left + plot.width}" y2="{y:.1f}" '
            f'stroke="{ZERO_LINE}" stroke-width="1" stroke-dasharray="6 4"/>'
        )
    ]


def _bars(plot: _Plot) -> list[str]:
    slot = plot.width / plot.days
    bar_width = slot * _BAR_SLOT_FILL / len(plot.series)
    zero_y = plot.y_at(0)
    parts = []
    for index, series in enumerate(plot.series):
        for day in range(1, plot.days + 1):
            value = series.values[day - 1]
            y = plot.y_at(value)
            x = (
                plot.left
                + slot * (day - 1)
                + slot * (1 - _BAR_SLOT_FILL) / 2
                + bar_width * index
            )
            top, height = (y, zero_y - y) if value >= 0 else (zero_y, y - zero_y)
            # Three states, matching the on-screen chart exactly: see
            # _Plot.day_bar_colour.
            bar_fill = plot.day_bar_colour(index, value)
            parts.append(
                f'<rect x="{x:.1f}" y="{top:.1f}" width="{bar_width:.1f}" '
                f'height="{max(0.0, height):.1f}" fill="{bar_fill}"/>'
            )
    return parts


def _lines(plot: _Plot) -> list[str]:
    parts = []
    for index, series in enumerate(plot.series):
        points = " ".join(
            f"{plot.x_at(day):.1f},{plot.y_at(series.values[day - 1]):.1f}"
            for day in range(1, plot.days + 1)
        )
        parts.append(
            f'<polyline points="{points}" fill="none" '
            f'stroke="{plot.line_colour(index)}" stroke-width="{_LINE_WIDTH}"/>'
        )
    return parts


def _curve(plot: _Plot) -> list[str]:
    if len(plot.totals) < 2:
        return []
    points = [
        (plot.x_at(day), plot.y_at(plot.totals[day - 1]))
        for day in range(1, plot.days + 1)
    ]
    path = [f"M {points[0][0]:.1f} {points[0][1]:.1f}"]
    for control_1, control_2, end in bezier_segments(points):
        path.append(
            f"C {control_1[0]:.1f} {control_1[1]:.1f}"
            f" {control_2[0]:.1f} {control_2[1]:.1f}"
            f" {end[0]:.1f} {end[1]:.1f}"
        )
    return [
        (
            f'<path d="{" ".join(path)}" fill="none" stroke="{plot.curve_colour()}" '
            f'stroke-width="{_CURVE_WIDTH}" stroke-linecap="round"/>'
        )
    ]


def _legend(plot: _Plot) -> list[str]:
    # The swatch has to be the colour actually drawn, which for one series
    # differs between the two renderings: green bars, a deep blue line.
    mark = plot.bar_colour if plot.with_curve else plot.line_colour
    entries = [(mark(i), s.label) for i, s in enumerate(plot.series)]
    if plot.with_curve:
        entries.append(
            (plot.curve_colour(), "Curve (total)" if len(plot.series) > 1 else "Curve")
        )
    parts = []
    x = plot.left
    for colour, label in entries:
        parts.append(
            f'<rect x="{x}" y="{_MARGIN_TOP}" width="{_LEGEND_SWATCH}" '
            f'height="{_LEGEND_SWATCH}" fill="{colour}"/>'
        )
        parts.append(
            f'<text x="{x + _LEGEND_SWATCH + 6}" y="{_MARGIN_TOP + 11}" '
            f'fill="{MUTED}" font-size="{_AXIS_FONT}">{_escape(label)}</text>'
        )
        x += _LEGEND_GAP
    return parts


def chart_svg(series, *, mode: str, labels, floor_pence: int = 0) -> str:
    """Render `series` as one SVG chart.

    Args:
        series: GraphSeries to plot; every one must have the same length.
        mode: "bar" or "line", matching the on-screen graph's two renderings.
        labels: (index, text) pairs for the x axis, 1-based like the days.
        floor_pence: the arranged overdraft, so a bar inside it reads amber
            rather than red. Zero means no facility, the previous behaviour.
    """
    with_curve = mode == "bar"
    plot = _Plot(series, with_curve=with_curve, floor_pence=floor_pence)
    body = _grid(plot)
    body += _bars(plot) if with_curve else _lines(plot)
    body += _zero_line(plot)
    if with_curve:
        body += _curve(plot)
    body += _x_labels(plot, labels=labels)
    body += _legend(plot)
    # Its own background rect, so the chart reads correctly wherever it is
    # embedded rather than depending on the page behind it.
    canvas = f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{PANEL}"/>'
    return (
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
        + canvas
        + "".join(body)
        + "</svg>"
    )
