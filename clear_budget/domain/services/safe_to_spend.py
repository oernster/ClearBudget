"""Sustainable spend - pure domain calculation over a day-by-day projection.

The single actionable number the forecasting engine produces: the most that
could be spent today with EVERY day of the window still clearing the safety
floor.

    sustainable_spend = min(P(d) for d in W) - F

where P(d) is the projected end-of-day balance assuming no discretionary
spend today, W is a bounded window of whole months from today and F is the
safety floor.

An earlier version stopped the window at the first day already below the
floor, reasoning that those days were lost whatever happened today. The
figure that produced was real yet it was not spendable: money spent today
lowers the lost days too, so a number computed by ignoring them funded its
own deficit. It could report hundreds of pounds as safe while the month
after collapsed by exactly that much more.

The result is signed and is NOT clamped here. A negative value is the sum the
window is short by, which is money to be found rather than spent; presenting
that is the UI's job.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from clear_budget.shared.errors import BudgetError


class SustainableError(BudgetError):
    """Raised when a sustainable-spend calculation is given unusable inputs."""


# How far ahead a sustainable figure must hold. Far enough that a month which
# collapses cannot be waved through as somebody else's problem, near enough
# that a forecast years out does not veto every penny today.
_DEFAULT_WINDOW_MONTHS = 4


@dataclass(frozen=True, slots=True)
class DayProjection:
    """Projected end-of-day bank balance for one calendar day."""

    day: date
    balance_pence: int


@dataclass(frozen=True, slots=True)
class CapacityStep:
    """What could be spent from `from_day` onward, plus what limits it.

    Attributes:
        from_day: The first day this figure applies to.
        amount_pence: Signed spendable value from that day on.
        binding_day: The minimum-balance day that set the figure.
    """

    from_day: date
    amount_pence: int
    binding_day: date


@dataclass(frozen=True, slots=True)
class SustainableResult:
    """What can be spent today and still leave the whole window standing.

    Attributes:
        amount_pence: Signed. Positive is spendable; negative is the amount
            the window is SHORT by, which no spending decision can fix.
        binding_day: The lowest day in the window, which set the figure.
        window_end: The last day considered.
        floor_pence: The buffer the figure was measured against.
    """

    amount_pence: int
    binding_day: date
    window_end: date
    floor_pence: int

    @property
    def is_sustainable(self) -> bool:
        """True when the window survives without any spending today."""
        return self.amount_pence >= 0


def _window_days(
    projection: Sequence[DayProjection], today: date, window_months: int
) -> list[DayProjection]:
    """Days from today to the end of the window, WITHOUT truncation.

    The deliberate difference from `_considered_days`: a day already below
    the floor is kept rather than ending the window. Dropping it is what let
    a figure be reported as safe while the month after it collapsed: the days
    that collapse were excluded from the very minimum meant to
    protect them. Spending today makes those days worse by exactly what is
    spent, so they have every right to veto it.

    Raises:
        SustainableError: If the window is not at least one month or the
            projection does not include today.
    """
    if window_months < 1:
        raise SustainableError("The window must be at least one month")
    future = sorted((d for d in projection if d.day >= today), key=lambda d: d.day)
    if not future or future[0].day != today:
        raise SustainableError("Projection must include today")

    months_seen: list[tuple[int, int]] = []
    within = []
    for day in future:
        key = (day.day.year, day.day.month)
        if key not in months_seen:
            if len(months_seen) == window_months:
                break
            months_seen.append(key)
        within.append(day)
    return within


def sustainable_spend(
    *,
    projection: Sequence[DayProjection],
    today: date,
    floor_pence: int = 0,
    window_months: int = _DEFAULT_WINDOW_MONTHS,
) -> SustainableResult:
    """The most that can be spent today with the WHOLE window still standing.

    The difference from `safe_to_spend` is that no day is excluded. That
    function stops at the first day already below the floor, on the ground
    that those days are lost whatever happens today, reporting the minimum
    of the healthy stretch before them. The figure that produces is real but
    it is not spendable: money spent today lowers the lost days too, so a
    number computed by ignoring them funds its own deficit.

    Here a window that cannot survive returns a NEGATIVE amount, which is the
    sum that would have to be found rather than spent. Nothing is safely
    spendable until it is.

    Raises:
        SustainableError: If the floor is negative, the window is shorter
            than a month or the projection does not include today.
    """
    if floor_pence < 0:
        raise SustainableError("Safety floor cannot be negative")
    within = _window_days(projection, today, window_months)
    binding = min(within, key=lambda d: d.balance_pence)
    return SustainableResult(
        amount_pence=binding.balance_pence - floor_pence,
        binding_day=binding.day,
        window_end=within[-1].day,
        floor_pence=floor_pence,
    )


def sustainable_capacity(
    *,
    projection: Sequence[DayProjection],
    today: date,
    floor_pence: int = 0,
    window_months: int = _DEFAULT_WINDOW_MONTHS,
) -> tuple[CapacityStep, ...]:
    """`sustainable_spend` from each remaining day of today's month onward.

    Same suffix-minimum shape as `spending_capacity`, over the untruncated
    window: waiting past a tight day still raises what a day can carry; it can
    never raise it past what the whole window will bear.
    """
    if floor_pence < 0:
        raise SustainableError("Safety floor cannot be negative")
    within = _window_days(projection, today, window_months)
    steps: list[CapacityStep] = []
    for index, day in enumerate(within):
        if day.day.month != today.month or day.day.year != today.year:
            break
        rest = within[index:]
        binding = min(rest, key=lambda d: d.balance_pence)
        amount = binding.balance_pence - floor_pence
        if steps and steps[-1].amount_pence == amount:
            continue
        steps.append(
            CapacityStep(from_day=day.day, amount_pence=amount, binding_day=binding.day)
        )
    return tuple(steps)
