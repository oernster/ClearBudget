"""Hover readout for the month graph, mixed into LineBarChart.

Extracted from _line_bar_chart to keep both modules under the 400-LOC limit
(tests/structural/test_loc_limits.py). Owns one concern: working out which
plotted point the pointer is over and reading that day's balance out beside
it. The geometry it hit-tests against is the chart's own, so a readout can
only ever land on a point that was actually drawn.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPen

from clear_budget.ui import ui_scale
from clear_budget.ui.utils.format_helpers import fmt

MODE_BAR = "bar"

_HOVER_DOT_PX = 6
# How near the pointer must come to a point to read it out.
_HOVER_SNAP_PX = 20
_READOUT_PAD_PX = 7
_READOUT_GAP_PX = 14
_READOUT_RADIUS_PX = 4


class ChartHoverMixin:
    """Pointer tracking plus the balance readout for one plotted point."""

    def mouseMoveEvent(self, event) -> None:
        hover = self._hit_test(event.position())
        if hover != self._hover:
            self._hover = hover
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if self._hover is not None:
            self._hover = None
            self.update()
        super().leaveEvent(event)

    def _hit_test(self, pos):
        """Return (series_idx, day) for the point under `pos`, else None."""
        geom = self._geometry()
        if geom is None:
            return None
        snap = ui_scale.px(_HOVER_SNAP_PX)
        day = self._day_at(geom, pos.x())
        best = None
        best_distance = None
        for idx in range(len(self._series)):
            # In bar mode the whole bar reads out, not only its top edge.
            if self._mode == MODE_BAR and self._bar_rect(geom, idx, day).contains(pos):
                return (idx, day)
            dx = self._x_at(geom, day) - pos.x()
            dy = self._y_at(geom, self._series[idx].values[day - 1]) - pos.y()
            distance = (dx * dx + dy * dy) ** 0.5
            if distance <= snap and (best_distance is None or distance < best_distance):
                best, best_distance = (idx, day), distance
        return best

    def _draw_hover(self, painter, geom) -> None:
        """Mark the hovered point and read out its balance beside it."""
        if self._hover is None:
            return
        idx, day = self._hover
        series = self._series[idx]
        value = series.values[day - 1]
        point = QPointF(self._x_at(geom, day), self._y_at(geom, value))
        radius = ui_scale.px(_HOVER_DOT_PX)
        painter.setBrush(self._plot_colour(idx))
        painter.setPen(QPen(QColor(self._tokens["text"]), 2))
        painter.drawEllipse(point, radius, radius)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        lines = [f"Day {day}: {fmt(value)}"]
        if len(self._series) > 1:
            lines.insert(0, series.label)
        self._draw_readout(painter, geom, point, lines)

    def _draw_readout(self, painter, geom, point, lines) -> None:
        """Draw the hover text in a panel box, kept inside the widget."""
        metrics = painter.fontMetrics()
        pad = ui_scale.px(_READOUT_PAD_PX)
        line_h = metrics.height()
        width = max(metrics.horizontalAdvance(line) for line in lines) + 2 * pad
        height = line_h * len(lines) + 2 * pad
        gap = ui_scale.px(_READOUT_GAP_PX)
        x = point.x() + gap
        if x + width > self.width():
            x = point.x() - gap - width
        y = point.y() - height - gap
        if y < geom[1]:
            y = point.y() + gap
        box = QRectF(max(0.0, x), max(0.0, y), width, height)
        radius = ui_scale.px(_READOUT_RADIUS_PX)
        painter.setBrush(QColor(self._tokens["panel_bg"]))
        painter.setPen(QPen(QColor(self._tokens["border"]), 1))
        painter.drawRoundedRect(box, radius, radius)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QColor(self._tokens["text"]))
        for row, line in enumerate(lines):
            painter.drawText(
                QRectF(box.x() + pad, box.y() + pad + row * line_h, width, line_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                line,
            )
