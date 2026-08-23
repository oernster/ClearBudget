"""Curve fitting for the month graph. Pure Python, no Qt.

The graph overlays ONE curve however many series are plotted: a smooth line
that FOLLOWS the day-end totals, passing through every day's actual value
(either the bank balance on its own or every card's balance added together).

It is deliberately an interpolation, not a smoothed average: a curve that cut
across a tall day would draw a balance the account never had. Monotone cubic
interpolation (Fritsch-Carlson) gives a curve that is smooth, goes through
every point and never bulges past a peak or a trough.
"""

from __future__ import annotations

# Beyond this the Fritsch-Carlson condition is violated and a segment could
# overshoot, so the pair of tangents is scaled back onto the circle of radius 3.
_MONOTONE_LIMIT = 3.0
# A cubic Bezier reproduces a Hermite segment when its control points sit one
# third of the span along each end tangent.
_CONTROL_FRACTION = 3.0


def daily_totals(series_values) -> tuple[int, ...]:
    """Sum the plotted series day by day, so one curve can cover them all.

    Truncates to the shortest series, so a ragged input cannot raise.
    """
    if not series_values:
        return ()
    return tuple(sum(day_values) for day_values in zip(*series_values))


def monotone_slopes(xs, ys) -> tuple[float, ...]:
    """Fritsch-Carlson tangents: smooth through every point, no overshoot.

    A local peak or trough gets a flat tangent, which is what stops the curve
    rising past a high day and dipping below a low one.
    """
    count = len(xs)
    if count < 2:
        return (0.0,) * count
    deltas = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(count - 1)]
    slopes = [float(deltas[0])]
    for i in range(1, count - 1):
        if deltas[i - 1] * deltas[i] <= 0:
            # A turning point: flatten it rather than carry momentum through.
            slopes.append(0.0)
        else:
            slopes.append((deltas[i - 1] + deltas[i]) / 2)
    slopes.append(float(deltas[-1]))
    for i, delta in enumerate(deltas):
        if delta == 0:
            slopes[i] = 0.0
            slopes[i + 1] = 0.0
            continue
        alpha = slopes[i] / delta
        beta = slopes[i + 1] / delta
        radius = (alpha * alpha + beta * beta) ** 0.5
        if radius > _MONOTONE_LIMIT:
            scale = _MONOTONE_LIMIT / radius
            slopes[i] = scale * alpha * delta
            slopes[i + 1] = scale * beta * delta
    return tuple(slopes)


def bezier_segments(points) -> tuple:
    """Cubic Bezier control points for a curve THROUGH every given point.

    Returns one (control_1, control_2, end_point) triple per segment, each
    point a plain (x, y) pair, ready to hand to a painter path.
    """
    if len(points) < 2:
        return ()
    xs = [float(x) for x, _y in points]
    ys = [float(y) for _x, y in points]
    slopes = monotone_slopes(xs, ys)
    segments = []
    for i in range(len(points) - 1):
        span = (xs[i + 1] - xs[i]) / _CONTROL_FRACTION
        segments.append(
            (
                (xs[i] + span, ys[i] + slopes[i] * span),
                (xs[i + 1] - span, ys[i + 1] - slopes[i + 1] * span),
                (xs[i + 1], ys[i + 1]),
            )
        )
    return tuple(segments)


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
