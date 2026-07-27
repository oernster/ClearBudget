"""LineBarChart - QPainter chart widget drawing labelled day series.

Renders one or more GraphSeries (day-end pence values across a month) as
either a line chart or a grouped bar chart, with a currency y-axis, day
x-axis, a highlighted zero line when the range crosses it and a legend when
more than one series is shown. No charting dependency; pure QPainter.

Chrome colours and the series palette both come from the active theme
(resolved per paint), so the chart follows the light/dark toggle: pastel
series on the dark canvas, saturated mid-tones on the light one.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from clear_budget.ui import ui_scale
from clear_budget.ui.utils.format_helpers import fmt

MODE_BAR = "bar"
MODE_LINE = "line"

_GRID_LINES = 4
_X_TICK_STEP_DAYS = 5
_BAR_SLOT_FILL = 0.8
_RANGE_PAD_FRACTION = 0.05

_MARGIN_LEFT = 78
_MARGIN_RIGHT = 14
_MARGIN_TOP = 14
_MARGIN_BOTTOM = 30
_LEGEND_ROW_HEIGHT = 22
_LEGEND_SWATCH = 12


def _active_palette():
    """Return (chrome tokens, series colours) for the applied theme.

    Resolved per paint rather than at construction, so an open graph repaints
    in the new theme the moment the tray toggle switches it.
    """
    from PySide6.QtWidgets import QApplication

    from clear_budget.ui import theme
    from clear_budget.ui.theme_tokens import series_colours_for, tokens_for

    name = theme.current_theme(QApplication.instance())
    return tokens_for(name), series_colours_for(name)


class LineBarChart(QWidget):
    """Draws GraphSeries values as a line or grouped bar chart."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._series = []
        self._mode = MODE_BAR
        self._tokens, self._colours = _active_palette()
        self.setMinimumHeight(ui_scale.px(260))

    def _series_colour(self, idx: int) -> QColor:
        """Return the plot colour for series `idx`, cycling the palette."""
        return QColor(self._colours[idx % len(self._colours)])

    def set_data(self, series, mode: str) -> None:
        """Replace the plotted series and mode, then repaint."""
        self._series = list(series)
        self._mode = mode
        self.update()

    def _value_range(self) -> tuple[int, int]:
        values = [v for s in self._series for v in s.values]
        low = min(0, min(values))
        high = max(0, max(values))
        if low == high:
            high = low + 1
        pad = max(1, int((high - low) * _RANGE_PAD_FRACTION))
        return low - pad if low < 0 else low, high + pad

    def paintEvent(self, event) -> None:
        self._tokens, self._colours = _active_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self._tokens["window_bg"]))
        if not self._series or not self._series[0].values:
            painter.setPen(QColor(self._tokens["text_muted"]))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "No data to plot"
            )
            painter.end()
            return

        legend_h = ui_scale.px(_LEGEND_ROW_HEIGHT) if len(self._series) > 1 else 0
        left = ui_scale.px(_MARGIN_LEFT)
        top = ui_scale.px(_MARGIN_TOP) + legend_h
        plot_w = self.width() - left - ui_scale.px(_MARGIN_RIGHT)
        plot_h = self.height() - top - ui_scale.px(_MARGIN_BOTTOM)
        if plot_w <= 0 or plot_h <= 0:
            painter.end()
            return

        low, high = self._value_range()
        days = len(self._series[0].values)

        def y_at(pence: int) -> float:
            return top + plot_h * (high - pence) / (high - low)

        def x_at(day: int) -> float:
            return left + plot_w * (day - 1) / max(1, days - 1)

        self._draw_grid(painter, left, top, plot_w, plot_h, low, high)
        if self._mode == MODE_BAR:
            self._draw_bars(painter, left, top, plot_w, plot_h, low, high, days)
        else:
            self._draw_lines(painter, x_at, y_at, days)
        if low < 0 < high:
            zero_pen = QPen(QColor(self._tokens["danger"]), 1, Qt.PenStyle.DashLine)
            painter.setPen(zero_pen)
            painter.drawLine(QPointF(left, y_at(0)), QPointF(left + plot_w, y_at(0)))
        self._draw_x_labels(painter, x_at, top + plot_h, days)
        if legend_h:
            self._draw_legend(painter, left)
        painter.end()

    def _draw_grid(self, painter, left, top, plot_w, plot_h, low, high) -> None:
        grid_pen = QPen(QColor(self._tokens["border"]), 1)
        text_pen = QColor(self._tokens["text_muted"])
        painter.setPen(grid_pen)
        for i in range(_GRID_LINES + 1):
            frac = i / _GRID_LINES
            y = top + plot_h * frac
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(left, y), QPointF(left + plot_w, y))
            pence = round(high - (high - low) * frac)
            painter.setPen(text_pen)
            painter.drawText(
                QRectF(0, y - ui_scale.px(9), left - ui_scale.px(6), ui_scale.px(18)),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                fmt(pence),
            )

    def _draw_lines(self, painter, x_at, y_at, days) -> None:
        for idx, series in enumerate(self._series):
            painter.setPen(QPen(self._series_colour(idx), 2))
            polygon = QPolygonF(
                [
                    QPointF(x_at(d), y_at(series.values[d - 1]))
                    for d in range(1, days + 1)
                ]
            )
            painter.drawPolyline(polygon)

    def _draw_bars(self, painter, left, top, plot_w, plot_h, low, high, days) -> None:
        slot_w = plot_w / days
        bar_w = slot_w * _BAR_SLOT_FILL / len(self._series)
        zero_y = top + plot_h * (high - 0) / (high - low)
        painter.setPen(Qt.PenStyle.NoPen)
        for idx, series in enumerate(self._series):
            colour = self._series_colour(idx)
            for day in range(1, days + 1):
                value = series.values[day - 1]
                y = top + plot_h * (high - value) / (high - low)
                x = (
                    left
                    + slot_w * (day - 1)
                    + slot_w * (1 - _BAR_SLOT_FILL) / 2
                    + bar_w * idx
                )
                rect = (
                    QRectF(x, y, bar_w, zero_y - y)
                    if value >= 0
                    else QRectF(x, zero_y, bar_w, y - zero_y)
                )
                painter.fillRect(rect, colour)

    def _draw_x_labels(self, painter, x_at, base_y, days) -> None:
        painter.setPen(QColor(self._tokens["text_muted"]))
        ticks = {1, days} | set(range(_X_TICK_STEP_DAYS, days, _X_TICK_STEP_DAYS))
        for day in sorted(ticks):
            painter.drawText(
                QRectF(
                    x_at(day) - ui_scale.px(14),
                    base_y + ui_scale.px(4),
                    ui_scale.px(28),
                    ui_scale.px(18),
                ),
                Qt.AlignmentFlag.AlignCenter,
                str(day),
            )

    def _draw_legend(self, painter, left) -> None:
        x = left
        y = ui_scale.px(4)
        swatch = ui_scale.px(_LEGEND_SWATCH)
        for idx, series in enumerate(self._series):
            painter.fillRect(QRectF(x, y + 3, swatch, swatch), self._series_colour(idx))
            painter.setPen(QColor(self._tokens["text_muted"]))
            label_rect = QRectF(
                x + swatch + ui_scale.px(6), y, ui_scale.px(180), ui_scale.px(18)
            )
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                series.label,
            )
            metrics = painter.fontMetrics()
            x = (
                label_rect.left()
                + metrics.horizontalAdvance(series.label)
                + ui_scale.px(18)
            )
