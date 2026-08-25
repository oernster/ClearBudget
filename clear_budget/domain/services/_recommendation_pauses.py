"""Pausing a reserve: the third lever, priced rather than encouraged.

Split from `recommendations` so that module holds the reasoning about timing
and income; re-exported from there, so nothing outside imports this by name.

Retiming and asking for income are the other two levers. This one is
different in kind and the difference is the whole point: it does not find
money, it stops putting money by. That always looks like an improvement in
the window on screen, because the relief lands inside it while the bill it
was for lands later, sometimes outside it entirely.

So a pause is never emitted as a bare win. Every one carries what it lifts
AND what the due month then arrives short by, measured the same way: a
re-walk of the same simulation with that commitment's hold-back removed. A
suggestion that cannot state its own price does not belong on the page.
"""

from __future__ import annotations

from dataclasses import dataclass

from clear_budget.domain.services._recommendation_trials import paused_from


@dataclass(frozen=True, slots=True)
class MonthLift:
    """What one month's low becomes when a pause is applied."""

    year: int
    month: int
    low_before_pence: int
    low_after_pence: int


@dataclass(frozen=True, slots=True)
class ReservePause:
    """Stopping one commitment's reserve from a month on, with its price.

    `lifts` names every month the pause measurably helps, in order.
    `shortfall_pence` is what the due month then arrives short by: the whole
    amount less whatever had already been put by when the pause begins.
    """

    name: str
    from_year: int
    from_month: int
    lifts: tuple[MonthLift, ...]
    shortfall_pence: int
    due_year: int
    due_month: int
    # Whether the due month is one the page is showing. Worth stating: when
    # it is not, the window carries the whole relief and none of the cost,
    # which is exactly when a pause reads best and deserves it least.
    due_within_horizon: bool = False


def _first_month_in_trouble(lows: tuple[int, ...], target: int) -> int | None:
    """The earliest month whose low falls short, else None.

    A pause is proposed from there rather than from the start of the window,
    because pausing earlier than the trouble costs more and buys nothing: the
    months before it were already clear.
    """
    return next((index for index, low in enumerate(lows) if low < target), None)


def reserve_pauses(
    *, months, reserves, target: int, lows_of
) -> tuple[ReservePause, ...]:
    """A priced pause for each commitment that would measurably help.

    `lows_of` re-runs the caller's own engine over a set of months and returns
    each month's UNAIDED low: where it bottoms out before any extra income is
    assumed. That is the reading the move sentences and the try-it-on panels
    use, so a pause's figures match the outlook rows printed above it. Passed
    in rather than imported, which keeps the import running one way only.

    Nothing is proposed while every month already clears the target: with no
    trouble to relieve, stopping a reserve is a cost with no benefit and the
    page has no business raising it.
    """
    if not reserves:
        return ()
    before = lows_of(months)
    from_index = _first_month_in_trouble(before, target)
    if from_index is None:
        return ()
    start = months[from_index]
    horizon = {(month.year, month.month) for month in months}
    found = []
    for reserve in reserves:
        after = lows_of(paused_from(months, reserve, from_index))
        lifts = tuple(
            MonthLift(
                year=month.year,
                month=month.month,
                low_before_pence=was,
                low_after_pence=now,
            )
            for month, was, now in zip(months, before, after)
            if now > was
        )
        if not lifts:
            continue
        # What had already been put by when the pause begins is kept; only
        # what would have been added from here on goes missing.
        opening_days = reserve.by_day[from_index]
        already_held = opening_days[0] if opening_days else 0
        found.append(
            ReservePause(
                name=reserve.name,
                from_year=start.year,
                from_month=start.month,
                lifts=lifts,
                shortfall_pence=max(0, reserve.amount_pence - already_held),
                due_year=reserve.due_year,
                due_month=reserve.due_month,
                due_within_horizon=(reserve.due_year, reserve.due_month) in horizon,
            )
        )
    return tuple(found)
