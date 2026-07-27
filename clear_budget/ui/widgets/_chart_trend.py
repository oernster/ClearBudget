"""Trend and inflection maths for the month graph. Pure Python, no Qt.

The graph overlays ONE trend curve however many series are plotted: a centred
moving average of the day-end totals, so a single line shows the direction of
travel through the month (the bank balance on its own, or every card's balance
added together). Inflection days are where that direction actually changes,
which is what the hover readout aims at.
"""

from __future__ import annotations

# Days averaged into each point, centred. Five (two either side) smooths the
# day-to-day steps that individual bills create while still turning inside a
# month; a wider window would flatten a real mid-month reversal.
TREND_WINDOW_DAYS = 5


def daily_totals(series_values) -> tuple[int, ...]:
    """Sum the plotted series day by day, so one curve can cover them all.

    Truncates to the shortest series, so a ragged input cannot raise.
    """
    if not series_values:
        return ()
    return tuple(sum(day_values) for day_values in zip(*series_values))


def moving_average(values, window: int = TREND_WINDOW_DAYS) -> tuple[int, ...]:
    """Centred moving average, clamped at the ends so every day gets a value.

    The ends average over the days that exist rather than being dropped or
    padded, which keeps the curve spanning the whole month.
    """
    if not values:
        return ()
    half = window // 2
    smoothed = []
    for index in range(len(values)):
        first = max(0, index - half)
        last = min(len(values), index + half + 1)
        span = values[first:last]
        smoothed.append(round(sum(span) / len(span)))
    return tuple(smoothed)


def trend_values(series_values, window: int = TREND_WINDOW_DAYS) -> tuple[int, ...]:
    """The smoothed day-end total for each day of the month."""
    return moving_average(daily_totals(series_values), window)


def inflection_days(values) -> tuple[int, ...]:
    """1-based days where the direction of travel changes (a peak or trough).

    A day counts when the change into it and the change out of it have
    opposite signs. Flat steps are skipped, so a plateau does not report every
    day inside it and a series that only ever falls reports none.
    """
    days = []
    for index in range(1, len(values) - 1):
        incoming = values[index] - values[index - 1]
        outgoing = values[index + 1] - values[index]
        if incoming == 0 or outgoing == 0:
            continue
        if (incoming > 0) != (outgoing > 0):
            days.append(index + 1)
    return tuple(days)
