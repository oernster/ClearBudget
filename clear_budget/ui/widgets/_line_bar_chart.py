"""LineBarChart - QPainter chart widget drawing labelled day series.

Renders one or more GraphSeries (day-end pence values across a month) as
either a line chart or a grouped bar chart, with a currency y-axis, day
x-axis, a highlighted zero line when the range crosses it and a legend.
The bar rendering carries a following curve, which passes through every
day's real value; the line rendering plots the days directly, so it needs
no curve over the top. Hovering a point reads out that day's balance. No
charting dependency; pure QPainter.

Chrome colours, the series palette and the curve colour all come from the
active theme (resolved per paint), so the chart follows the light/dark
toggle: pastel series on the dark canvas, saturated mid-tones on the light.

The axes chrome (measured y-axis margin, grid, day labels, legend) lives in
_chart_axes, the colour each mark takes in _chart_colours and the hover
readout in _chart_hover, one concern per file.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from clear_budget.application.reporting.curve import (
    bezier_segments,
    daily_totals,
    inflection_days,
)
from clear_budget.ui import ui_scale
from clear_budget.ui.widgets._chart_axes import ChartAxesMixin
from clear_budget.ui.widgets._chart_colours import (
    ChartColoursMixin,
    active_palette,
    solo_palette,
)
from clear_budget.ui.widgets._chart_hover import ChartHoverMixin

MODE_BAR = "bar"
MODE_LINE = "line"

_BAR_SLOT_FILL = 0.8
_RANGE_PAD_FRACTION = 0.05

_MARGIN_RIGHT = 14
_MARGIN_TOP = 14
_MARGIN_BOTTOM = 30
_LEGEND_ROW_HEIGHT = 22

_CURVE_PEN_PX = 3
# A marker sits on each direction change, so the hover readout has something
# to aim at rather than the user hunting along a bare line.
_INFLECTION_DOT_PX = 4
_HOVER_DOT_PX = 6
# How near the pointer must come to a point to read it out.
_HOVER_SNAP_PX = 20
_READOUT_PAD_PX = 7
_READOUT_GAP_PX = 14
_READOUT_RADIUS_PX = 4
# Thin on purpose: the floor is a threshold to read a bar against, so a
# heavier stroke would compete with the bars it exists to qualify.
_FLOOR_LINE_WIDTH_PX = 1


class LineBarChart(ChartAxesMixin, ChartColoursMixin, ChartHoverMixin, QWidget):
    """Draws GraphSeries values as a line or grouped bar chart."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._series = []
        self._mode = MODE_BAR
        self._hover = None
        self._tokens, self._colours, self._curve_colour = active_palette()
        self._solo_colours = solo_palette()
        self._overdraft_limit_pence = 0
        # One floor value per day of the plotted month; empty means the chart
        # was given none, which is how a card plot and every older caller
        # behave; it is drawn exactly as before.
        self._floor_values: list[int] = []
        self.setMinimumHeight(ui_scale.px(260))
        # Hover readouts need move events without a button held down.
        self.setMouseTracking(True)

    def set_data(self, series, mode: str) -> None:
        """Replace the plotted series and mode, then repaint."""
        self._series = list(series)
        self._mode = mode
        self._hover = None
        self.update()

    def set_overdraft_limit_pence(self, limit_pence: int) -> None:
        """The arranged overdraft a bar may dip into before it reads as red.

        Zero, the default, means no facility: the floor is zero and every
        below-zero bar is red, which is what the chart did before there was
        anything to tell it otherwise. A card chart never sets this, since an
        overdraft is a bank arrangement and a card has its own limit.
        """
        self._overdraft_limit_pence = max(0, int(limit_pence))
        self.update()

    def set_reserve_floor_values(self, values) -> None:
        """The floor for each day of the plotted month, in pence.

        Drawn as a line and used to tell a day in credit apart from a day
        that is genuinely free. Passing nothing restores the older reading,
        where only zero and the arranged overdraft divide the bars.
        """
        self._floor_values = [int(v) for v in values]
        self.update()

    def _floor_at(self, day: int) -> int | None:
        """The floor on `day`; None when this chart was given no floor."""
        if not self._floor_values or day > len(self._floor_values):
            return None
        return self._floor_values[day - 1]

    def _curve_values(self) -> tuple[int, ...]:
        """The day-end total the curve follows, across every plotted series.

        With one series this IS that series, so the curve traces its own bars
        rather than an average of them.
        """
        return daily_totals([s.values for s in self._series])

    def _curve_shown(self) -> bool:
        """Whether the curve is drawn, which is bar mode only.

        The line rendering already passes through every day's real value, so
        a curve over the top of it duplicates the line it sits on.
        """
        return self._mode == MODE_BAR

    def _value_range(self) -> tuple[int, int]:
        values = [v for s in self._series for v in s.values]
        if self._curve_shown():
            # The curve shares the axis, so it has to fit inside it.
            values += list(self._curve_values())
        low = min(0, min(values))
        high = max(0, max(values))
        if low == high:
            high = low + 1
        pad = max(1, int((high - low) * _RANGE_PAD_FRACTION))
        return low - pad if low < 0 else low, high + pad

    # ---- geometry -----------------------------------------------------------
    def _geometry(self):
        """Return (left, top, plot_w, plot_h, days, low, high) or None.

        Shared by painting and hit-testing, so a hover lands on exactly the
        point that was drawn.
        """
        if not self._series or not self._series[0].values:
            return None
        top = ui_scale.px(_MARGIN_TOP) + ui_scale.px(_LEGEND_ROW_HEIGHT)
        low, high = self._value_range()
        left = self._left_margin(low, high)
        plot_w = self.width() - left - ui_scale.px(_MARGIN_RIGHT)
        plot_h = self.height() - top - ui_scale.px(_MARGIN_BOTTOM)
        if plot_w <= 0 or plot_h <= 0:
            return None
        return (left, top, plot_w, plot_h, len(self._series[0].values), low, high)

    @staticmethod
    def _y_at(geom, pence: int) -> float:
        _left, top, _plot_w, plot_h, _days, low, high = geom
        return top + plot_h * (high - pence) / (high - low)

    @staticmethod
    def _x_at(geom, day: int) -> float:
        left, _top, plot_w, _plot_h, days, _low, _high = geom
        return left + plot_w * (day - 1) / max(1, days - 1)

    def _day_at(self, geom, x: float) -> int:
        """The day whose column or point the given x falls nearest."""
        left, _top, plot_w, _plot_h, days, _low, _high = geom
        if self._mode == MODE_BAR:
            day = int((x - left) / (plot_w / days)) + 1
        else:
            day = round((x - left) / plot_w * max(1, days - 1)) + 1
        return max(1, min(days, day))

    def _bar_rect(self, geom, series_idx: int, day: int) -> QRectF:
        """The rectangle drawn for one series' bar on one day."""
        left, top, plot_w, plot_h, days, low, high = geom
        slot_w = plot_w / days
        bar_w = slot_w * _BAR_SLOT_FILL / len(self._series)
        zero_y = top + plot_h * (high - 0) / (high - low)
        value = self._series[series_idx].values[day - 1]
        y = self._y_at(geom, value)
        x = (
            left
            + slot_w * (day - 1)
            + slot_w * (1 - _BAR_SLOT_FILL) / 2
            + bar_w * series_idx
        )
        if value >= 0:
            return QRectF(x, y, bar_w, zero_y - y)
        return QRectF(x, zero_y, bar_w, y - zero_y)

    # ---- painting -----------------------------------------------------------
    def paintEvent(self, event) -> None:
        # Colours are re-resolved per paint so a theme switch repaints; the
        # overdraft limit is NOT, because it is data the caller set and not a
        # property of the theme. Resetting it here silently painted every
        # below-zero bar red however large the arranged facility was.
        self._tokens, self._colours, self._curve_colour = active_palette()
        self._solo_colours = solo_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self._tokens["window_bg"]))
        geom = self._geometry()
        if geom is None:
            painter.setPen(QColor(self._tokens["text_muted"]))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "No data to plot"
            )
            painter.end()
            return

        _left, _top, _plot_w, _plot_h, days, low, high = geom
        self._draw_grid(painter, geom)
        if self._mode == MODE_BAR:
            self._draw_bars(painter, geom)
        else:
            self._draw_lines(painter, geom)
        self._draw_floor(painter, geom)
        if low < 0 < high:
            zero_pen = QPen(QColor(self._tokens["danger"]), 1, Qt.PenStyle.DashLine)
            painter.setPen(zero_pen)
            y_zero = self._y_at(geom, 0)
            painter.drawLine(
                QPointF(self._x_at(geom, 1), y_zero),
                QPointF(self._x_at(geom, days), y_zero),
            )
        if self._curve_shown():
            self._draw_curve(painter, geom)
        self._draw_x_labels(painter, geom)
        self._draw_legend(painter, geom)
        self._draw_hover(painter, geom)
        painter.end()

    def _draw_lines(self, painter, geom) -> None:
        _left, _top, _plot_w, _plot_h, days, _low, _high = geom
        dot = ui_scale.px(_INFLECTION_DOT_PX)
        for idx, series in enumerate(self._series):
            colour = self._plot_colour(idx)
            painter.setPen(QPen(colour, 2))
            painter.drawPolyline(
                QPolygonF(
                    [
                        QPointF(
                            self._x_at(geom, d), self._y_at(geom, series.values[d - 1])
                        )
                        for d in range(1, days + 1)
                    ]
                )
            )
            # Mark the direction changes, the points the readout snaps to.
            painter.setBrush(colour)
            painter.setPen(Qt.PenStyle.NoPen)
            for day in inflection_days(series.values):
                painter.drawEllipse(
                    QPointF(
                        self._x_at(geom, day), self._y_at(geom, series.values[day - 1])
                    ),
                    dot,
                    dot,
                )
            painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_bars(self, painter, geom) -> None:
        _left, _top, _plot_w, _plot_h, days, _low, _high = geom
        painter.setPen(Qt.PenStyle.NoPen)
        # Four states per day: free; in credit but spoken for; inside an
        # arranged overdraft; past it. See _bar_colour_for.
        for idx, series in enumerate(self._series):
            colour = self._plot_colour(idx)
            for day in range(1, days + 1):
                bar_colour = self._bar_colour_for(
                    series.values[day - 1], colour, floor_pence=self._floor_at(day)
                )
                painter.fillRect(self._bar_rect(geom, idx, day), bar_colour)

    def _draw_floor(self, painter, geom) -> None:
        """The floor across the month, so the shape of the reserve is visible.

        A thin dashed line rather than a filled band: it is a threshold to
        read a bar against, never a quantity of its own; a fill would
        compete with the bars it exists to qualify.
        """
        _left, _top, _plot_w, _plot_h, days, _low, _high = geom
        if not self._floor_values:
            return
        pen = QPen(QColor(self._tokens["border"]))
        pen.setWidth(_FLOOR_LINE_WIDTH_PX)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(self._x_at(geom, day), self._y_at(geom, floor))
                    for day in range(1, days + 1)
                    if (floor := self._floor_at(day)) is not None
                ]
            )
        )
        painter.setPen(Qt.PenStyle.NoPen)

    def _draw_curve(self, painter, geom) -> None:
        """Overlay a smooth curve FOLLOWING the totals, in the curve colour.

        Monotone cubic segments, so the curve reaches each day's real value and
        never bulges past a tall day or below a low one.
        """
        _left, _top, _plot_w, _plot_h, days, _low, _high = geom
        values = self._curve_values()
        if len(values) < 2:
            return
        points = [
            (self._x_at(geom, d), self._y_at(geom, values[d - 1]))
            for d in range(1, days + 1)
        ]
        path = QPainterPath(QPointF(*points[0]))
        for control_1, control_2, end in bezier_segments(points):
            path.cubicTo(QPointF(*control_1), QPointF(*control_2), QPointF(*end))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(
                self._active_curve_colour(),
                ui_scale.px(_CURVE_PEN_PX),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        painter.drawPath(path)
