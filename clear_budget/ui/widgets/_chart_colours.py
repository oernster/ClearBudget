"""Mark colours for the month graph, mixed into LineBarChart.

Which colour every drawn mark takes: the theme palettes resolved per paint,
the role colours a lone series is given and the four-state reading of one
day's bar against zero, its reserve floor and the arranged overdraft. Split
from _line_bar_chart so each file holds one concern, the same shape as the
axes chrome in _chart_axes and the hover readout in _chart_hover.

The palettes are functions rather than constants because the chart follows
the light/dark toggle: they are re-resolved on every paint.
"""

from PySide6.QtGui import QColor

# Declared here rather than imported from _line_bar_chart, which imports this
# module; the same shape as _chart_hover.
MODE_BAR = "bar"


def active_palette():
    """Return (chrome tokens, series colours, curve colour) for the theme.

    Resolved per paint rather than at construction, so an open graph repaints
    in the new theme the moment the tray toggle switches it.
    """
    from PySide6.QtWidgets import QApplication

    from clear_budget.ui import theme
    from clear_budget.ui.theme_tokens import (
        curve_colour_for,
        series_colours_for,
        tokens_for,
    )

    name = theme.current_theme(QApplication.instance())
    return tokens_for(name), series_colours_for(name), curve_colour_for(name)


def solo_palette():
    """Role colours for one series: line, bar, curve, in-facility, under-floor."""
    from PySide6.QtWidgets import QApplication

    from clear_budget.ui import theme
    from clear_budget.ui.theme_tokens import (
        chart_bar_colour_for,
        chart_bar_under_floor_colour_for,
        chart_bar_within_facility_colour_for,
        chart_line_colour_for,
        solo_curve_colour_for,
    )

    name = theme.current_theme(QApplication.instance())
    return (
        chart_line_colour_for(name),
        chart_bar_colour_for(name),
        solo_curve_colour_for(name),
        chart_bar_within_facility_colour_for(name),
        chart_bar_under_floor_colour_for(name),
    )


class ChartColoursMixin:
    """The colour each plotted mark takes, mixed into LineBarChart."""

    def _bar_colour_for(
        self, value_pence: int, colour: QColor, *, floor_pence: int | None = None
    ) -> QColor:
        """Four-state fill for one day's bar, read against what it owes.

        At or above zero the day is in credit. It keeps the series colour only
        while it also clears its floor; under the floor it is dimmed, because
        the money is there but is already spoken for. Below zero but no
        further than the arranged overdraft it is amber: the facility absorbs
        that day, so red would say a payment bounced when none did. Past the
        facility it is red, where one would.
        """
        if value_pence >= 0:
            _l, _b, _c, _w, under = self._solo_colours
            if floor_pence is not None and value_pence < floor_pence:
                return QColor(under)
            return colour
        _line, _bar, _curve, within, _under = self._solo_colours
        if value_pence >= -self._overdraft_limit_pence:
            return QColor(within)
        return QColor(self._tokens["danger"])

    def _series_colour(self, idx: int) -> QColor:
        """Return the palette colour for series `idx`, cycling the palette."""
        return QColor(self._colours[idx % len(self._colours)])

    def _solo(self) -> bool:
        """Whether this chart plots exactly one series."""
        return len(self._series) == 1

    def _plot_colour(self, idx: int) -> QColor:
        """The colour series `idx` is ACTUALLY drawn in, for the current mode.

        A single series takes a role colour: a deep blue as a line, green as
        bars. The line stays neutral because one stroke spans a whole month,
        so green there read as "in credit" over days that were not; a bar is
        one day, so green states a fact about a day that really is.
        With several series the palette wins, because telling one card from
        another is the only job the colour has there.
        """
        line_colour, bar_colour, _curve, _within, _under = self._solo_colours
        if not self._solo():
            return self._series_colour(idx)
        return QColor(bar_colour if self._mode == MODE_BAR else line_colour)

    def _active_curve_colour(self) -> QColor:
        """The curve's colour: the line's blue alone, else its own hue."""
        _line, _bar, solo_curve, _within, _under = self._solo_colours
        return QColor(solo_curve if self._solo() else self._curve_colour)
