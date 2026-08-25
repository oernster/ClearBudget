"""Bar and line charts as inline SVG. Pure Python, no Qt and no I/O.

The on-screen graph is QPainter, which cannot go into a file anyone can open
in a browser. Rather than screenshot the widget, the export redraws the same
series with the same rules as vector SVG: it stays sharp at any zoom, weighs
almost nothing, needs no image file beside the HTML and (being a pure string
build) is testable without a QApplication.

The fixed dark palette and the layout metrics live in _chart_svg_theme, so
this file holds the drawing and that one holds what it draws with, the same
shape the on-screen chart has in ui.theme_tokens and ui.ui_scale.

The chart rules match the widget exactly (see _line_bar_chart.py): the bar
rendering carries the following curve through every day's real value, the
line rendering plots the days directly and needs none, the axis always
includes zero and the zero line is drawn when the range crosses it.
"""

from __future__ import annotations

from math import ceil

from clear_budget.application.reporting import _chart_svg_theme as theme
from clear_budget.application.reporting.curve import bezier_segments, daily_totals


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

    def __init__(
        self,
        series,
        *,
        with_curve: bool,
        floor_pence: int = 0,
        floor_values=None,
    ) -> None:
        self.series = list(series)
        # The reserve floor for each day of the month. Empty means the
        # caller gave none, which is how a card plot and every export
        # made before reserves existed behave.
        self.floor_values = (
            [] if floor_values is None else [int(v) for v in floor_values]
        )
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
        pad = max(1, int((high - low) * theme.RANGE_PAD_FRACTION))
        self.low = low - pad if low < 0 else low
        self.high = high + pad
        # The tick labels, top to bottom; the margin is sized to the widest.
        self.y_labels = tuple(
            _money(round(self.high - (self.high - self.low) * i / theme.GRID_LINES))
            for i in range(theme.GRID_LINES + 1)
        )
        widest = max(len(label) for label in self.y_labels)
        estimated = (
            ceil(widest * theme.AXIS_CHAR_WIDTH)
            + theme.AXIS_LABEL_GAP
            + theme.AXIS_LABEL_INSET
        )
        self.left = max(theme.MARGIN_LEFT_MIN, estimated)
        self.top = theme.MARGIN_TOP + theme.LEGEND_HEIGHT
        self.width = theme.WIDTH - self.left - theme.MARGIN_RIGHT
        self.height = theme.HEIGHT - self.top - theme.MARGIN_BOTTOM

    def y_at(self, pence: float) -> float:
        return self.top + self.height * (self.high - pence) / (self.high - self.low)

    def x_at(self, day: int) -> float:
        return self.left + self.width * (day - 1) / max(1, self.days - 1)

    def colour(self, index: int) -> str:
        return theme.SERIES[index % len(theme.SERIES)]

    @property
    def solo(self) -> bool:
        """Whether this plot carries exactly one series."""
        return len(self.series) == 1

    def bar_colour(self, index: int) -> str:
        """The fill for a positive bar of series `index`."""
        return theme.SOLO_BAR if self.solo else self.colour(index)

    def reserve_floor_at(self, day: int) -> int | None:
        """The reserve floor on `day`; None when this plot was given none."""
        if not self.floor_values or day > len(self.floor_values):
            return None
        return self.floor_values[day - 1]

    def day_bar_colour(self, index: int, value: int, day: int = 0) -> str:
        """Four-state fill for one day, matching the on-screen chart.

        In credit and clear of its reserve floor; in credit but under it,
        so the money is there and already spoken for; below zero inside
        an arranged overdraft, which the facility absorbs; past that
        facility, where a payment really would bounce.
        """
        if value >= 0:
            floor = self.reserve_floor_at(day)
            if floor is not None and value < floor:
                return theme.SOLO_BAR_UNDER
            return self.bar_colour(index)
        return theme.SOLO_BAR_WITHIN if value >= self.floor_pence else theme.ZERO_LINE

    def line_colour(self, index: int) -> str:
        """The stroke for the plotted line of series `index`."""
        return theme.SOLO_LINE if self.solo else self.colour(index)

    def curve_colour(self) -> str:
        """The following curve's stroke.

        The line's blue over a lone series' bars; its own hue when several
        series share the axis, where it must not read as one more of them.
        """
        return theme.SOLO_CURVE if self.solo else theme.CURVE


def _axis_text(x, y, anchor: str, label) -> str:
    """One piece of axis or legend text, in the chart's muted label style.

    The three callers differ only in where the text sits and how it hangs off
    that point, so the style is written once.
    """
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'fill="{theme.MUTED}" font-size="{theme.AXIS_FONT}">'
        f"{_escape(label)}</text>"
    )


def _grid(plot: _Plot) -> list[str]:
    parts = []
    # The same labels the margin was estimated from, so they always fit.
    for i, label in enumerate(plot.y_labels):
        fraction = i / theme.GRID_LINES
        y = plot.top + plot.height * fraction
        parts.append(
            f'<line x1="{plot.left}" y1="{y:.1f}" '
            f'x2="{plot.left + plot.width}" y2="{y:.1f}" '
            f'stroke="{theme.GRID}" stroke-width="1"/>'
        )
        parts.append(
            _axis_text(plot.left - theme.AXIS_LABEL_GAP, f"{y + 4:.1f}", "end", label)
        )
    return parts


def _x_labels(plot: _Plot, *, labels) -> list[str]:
    base = plot.top + plot.height + 18
    parts = []
    for day, label in labels:
        parts.append(_axis_text(f"{plot.x_at(day):.1f}", base, "middle", label))
    return parts


def _zero_line(plot: _Plot) -> list[str]:
    if not plot.low < 0 < plot.high:
        return []
    y = plot.y_at(0)
    return [
        (
            f'<line x1="{plot.left}" y1="{y:.1f}" '
            f'x2="{plot.left + plot.width}" y2="{y:.1f}" '
            f'stroke="{theme.ZERO_LINE}" stroke-width="1" stroke-dasharray="6 4"/>'
        )
    ]


def _floor_line(plot: _Plot) -> list[str]:
    """The reserve floor across the month, so its shape is visible.

    A thin dashed polyline rather than a filled band, matching the
    on-screen chart: it qualifies the bars it crosses rather than
    standing as a quantity beside them.
    """
    points = [
        f"{plot.x_at(day):.1f},{plot.y_at(floor):.1f}"
        for day in range(1, plot.days + 1)
        if (floor := plot.reserve_floor_at(day)) is not None
    ]
    if len(points) < 2:
        return []
    return [
        (
            f'<polyline points="{" ".join(points)}" fill="none" '
            f'stroke="{theme.MUTED}" stroke-width="{theme.FLOOR_WIDTH}" '
            f'stroke-dasharray="{theme.FLOOR_DASH}"/>'
        )
    ]


def _bars(plot: _Plot) -> list[str]:
    slot = plot.width / plot.days
    bar_width = slot * theme.BAR_SLOT_FILL / len(plot.series)
    zero_y = plot.y_at(0)
    parts = []
    for index, series in enumerate(plot.series):
        for day in range(1, plot.days + 1):
            value = series.values[day - 1]
            y = plot.y_at(value)
            x = (
                plot.left
                + slot * (day - 1)
                + slot * (1 - theme.BAR_SLOT_FILL) / 2
                + bar_width * index
            )
            top, height = (y, zero_y - y) if value >= 0 else (zero_y, y - zero_y)
            # Four states, matching the on-screen chart exactly: see
            # _Plot.day_bar_colour.
            bar_fill = plot.day_bar_colour(index, value, day)
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
            f'stroke="{plot.line_colour(index)}" stroke-width="{theme.LINE_WIDTH}"/>'
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
            f'stroke-width="{theme.CURVE_WIDTH}" stroke-linecap="round"/>'
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
            f'<rect x="{x}" y="{theme.MARGIN_TOP}" width="{theme.LEGEND_SWATCH}" '
            f'height="{theme.LEGEND_SWATCH}" fill="{colour}"/>'
        )
        parts.append(
            _axis_text(
                x + theme.LEGEND_SWATCH + 6, theme.MARGIN_TOP + 11, "start", label
            )
        )
        x += theme.LEGEND_GAP
    return parts


def chart_svg(
    series, *, mode: str, labels, floor_pence: int = 0, floor_values=None
) -> str:
    """Render `series` as one SVG chart.

    Args:
        series: GraphSeries to plot; every one must have the same length.
        mode: "bar" or "line", matching the on-screen graph's two renderings.
        labels: (index, text) pairs for the x axis, 1-based like the days.
        floor_pence: the arranged overdraft, so a bar inside it reads amber
            rather than red. Zero means no facility, the previous behaviour.
        floor_values: the reserve floor for each day of the month, so a day
            in credit but already spoken for reads dimmed and the floor is
            drawn across the chart. None means none was given.
    """
    with_curve = mode == "bar"
    plot = _Plot(
        series,
        with_curve=with_curve,
        floor_pence=floor_pence,
        floor_values=floor_values,
    )
    body = _grid(plot)
    body += _bars(plot) if with_curve else _lines(plot)
    body += _floor_line(plot)
    body += _zero_line(plot)
    if with_curve:
        body += _curve(plot)
    body += _x_labels(plot, labels=labels)
    body += _legend(plot)
    # Its own background rect, so the chart reads correctly wherever it is
    # embedded rather than depending on the page behind it.
    canvas = (
        f'<rect width="{theme.WIDTH}" height="{theme.HEIGHT}" fill="{theme.PANEL}"/>'
    )
    return (
        f'<svg viewBox="0 0 {theme.WIDTH} {theme.HEIGHT}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
        + canvas
        + "".join(body)
        + "</svg>"
    )
