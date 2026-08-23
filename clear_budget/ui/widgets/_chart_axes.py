"""Axes chrome for the month graph, mixed into LineBarChart.

The y-axis labels with their measured left margin, the horizontal grid, the
day numbers along the x axis and the legend: the chart's frame, as distinct
from the plotted data. Split from _line_bar_chart so each file holds one
concern, the same shape as the hover readout in _chart_hover.

The left margin is MEASURED per paint from the widest y-axis label, so a
large balance ("£12,345,678.90") never truncates against the dialog edge.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPen

from clear_budget.ui import ui_scale
from clear_budget.ui.utils.format_helpers import fmt

_GRID_LINES = 4
_X_TICK_STEP_DAYS = 5

# The floor keeps the plot from hugging the edge when the labels happen to be
# short.
_MARGIN_LEFT_MIN = 78
# Gap between a y-axis label's right edge and the plot, matching the rect the
# labels are right-aligned into, plus a small inset so the label's own left
# edge never touches the widget border.
_AXIS_LABEL_GAP = 6
_AXIS_LABEL_INSET = 4

_LEGEND_SWATCH = 12
_LEGEND_LABEL_WIDTH = 180

_CURVE_LABEL = "Curve"
_CURVE_TOTAL_LABEL = "Curve (total)"


class ChartAxesMixin:
    """Grid, axis labels, measured margin and legend for LineBarChart."""

    def _y_labels(self, low: int, high: int) -> tuple[str, ...]:
        """The y-axis tick labels, top to bottom, one per grid line."""
        return tuple(
            fmt(round(high - (high - low) * i / _GRID_LINES))
            for i in range(_GRID_LINES + 1)
        )

    def _left_margin(self, low: int, high: int) -> int:
        """The left margin, measured so the widest y label fits inside it."""
        metrics = self.fontMetrics()
        widest = max(
            metrics.horizontalAdvance(label) for label in self._y_labels(low, high)
        )
        measured = (
            widest + ui_scale.px(_AXIS_LABEL_GAP) + ui_scale.px(_AXIS_LABEL_INSET)
        )
        return max(ui_scale.px(_MARGIN_LEFT_MIN), measured)

    def _draw_grid(self, painter, geom) -> None:
        left, top, plot_w, plot_h, _days, low, high = geom
        grid_pen = QPen(QColor(self._tokens["border"]), 1)
        text_pen = QColor(self._tokens["text_muted"])
        # The same labels the margin was measured from, so they always fit.
        for i, label in enumerate(self._y_labels(low, high)):
            frac = i / _GRID_LINES
            y = top + plot_h * frac
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(left, y), QPointF(left + plot_w, y))
            painter.setPen(text_pen)
            painter.drawText(
                QRectF(
                    0,
                    y - ui_scale.px(9),
                    left - ui_scale.px(_AXIS_LABEL_GAP),
                    ui_scale.px(18),
                ),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

    def _draw_x_labels(self, painter, geom) -> None:
        _left, top, _plot_w, plot_h, days, _low, _high = geom
        base_y = top + plot_h
        painter.setPen(QColor(self._tokens["text_muted"]))
        ticks = {1, days} | set(range(_X_TICK_STEP_DAYS, days, _X_TICK_STEP_DAYS))
        for day in sorted(ticks):
            painter.drawText(
                QRectF(
                    self._x_at(geom, day) - ui_scale.px(14),
                    base_y + ui_scale.px(4),
                    ui_scale.px(28),
                    ui_scale.px(18),
                ),
                Qt.AlignmentFlag.AlignCenter,
                str(day),
            )

    def _draw_legend(self, painter, geom) -> None:
        left = geom[0]
        x = left
        y = ui_scale.px(4)
        swatch = ui_scale.px(_LEGEND_SWATCH)
        entries = [
            (self._plot_colour(idx), series.label)
            for idx, series in enumerate(self._series)
        ]
        if self._curve_shown():
            curve_label = _CURVE_TOTAL_LABEL if len(self._series) > 1 else _CURVE_LABEL
            entries.append((self._active_curve_colour(), curve_label))
        for colour, label in entries:
            painter.fillRect(QRectF(x, y + 3, swatch, swatch), colour)
            painter.setPen(QColor(self._tokens["text_muted"]))
            painter.drawText(
                QRectF(
                    x + swatch + ui_scale.px(6),
                    y,
                    ui_scale.px(_LEGEND_LABEL_WIDTH),
                    ui_scale.px(18),
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
            x += swatch + ui_scale.px(_LEGEND_LABEL_WIDTH)
