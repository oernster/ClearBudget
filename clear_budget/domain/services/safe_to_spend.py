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
    """What can be spent today with every month that still stands left standing.

    Attributes:
        amount_pence: Signed. Positive is spendable. Negative only when not
            even the current month clears the floor, in which case it is the
            sum the window is SHORT by rather than an amount to spend.
        binding_day: The lowest day of the covered stretch, which set the
            figure.
        covered_end: The last day the figure makes a promise about: the end of
            the last month that clears the floor with no spending at all.
        floor_pence: The buffer the figure was measured against.
        shortfall_pence: How far the worst day BEYOND the covered stretch
            falls under the floor. It is 0 when the whole window stands. It is
            never subtracted from the figure: it is a gap that exists whether
            or not anything is spent today.
        shortfall_day: The day that shortfall lands on. None when there
            is no such day.
    """

    amount_pence: int
    binding_day: date
    covered_end: date
    floor_pence: int
    shortfall_pence: int = 0
    shortfall_day: date | None = None

    @property
    def is_sustainable(self) -> bool:
        """True when the covered stretch survives without any spending today."""
        return self.amount_pence >= 0

    @property
    def has_shortfall(self) -> bool:
        """True when a month past the covered stretch cannot be saved by thrift."""
        return self.shortfall_day is not None


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


def _covered_and_beyond(
    within: Sequence[DayProjection], floor_pence: int
) -> tuple[list[DayProjection], list[DayProjection]]:
    """Split the window at the first month that cannot clear the floor unaided.

    The covered stretch is the longest run of whole months from today whose
    own lowest day still clears the floor with nothing spent. Everything from
    the first failing month onward is beyond it, INCLUDING any later month
    that looks healthy on paper: a month after a collapse is projected from
    that collapse, so promising it would be promising a balance that cannot
    be reached.

    Splitting by month rather than by day is what makes the answer speakable.
    "Everything through October holds" is a sentence a person can check
    against the projection; "everything up to the thirteenth of November"
    describes a boundary that exists only inside the arithmetic.
    """
    covered: list[DayProjection] = []
    months: dict[tuple[int, int], list[DayProjection]] = {}
    for day in within:
        months.setdefault((day.day.year, day.day.month), []).append(day)
    for key in sorted(months):
        days = months[key]
        if min(d.balance_pence for d in days) - floor_pence < 0:
            break
        covered += days
    beyond = within[len(covered) :]
    return covered, beyond


def sustainable_spend(
    *,
    projection: Sequence[DayProjection],
    today: date,
    floor_pence: int = 0,
    window_months: int = _DEFAULT_WINDOW_MONTHS,
) -> SustainableResult:
    """The most that can be spent today leaving every surviving month standing.

    A month already under the floor with NOTHING spent is not a spending
    limit; it is a shortfall. Letting it veto the figure answers "does my
    budget hold?" in the slot reserved for "what can I spend?". It reports
    nothing spendable while the account still has real headroom in front of
    it. So the figure is bounded at the end of the last month that clears the
    floor unaided and the shortfall beyond is carried separately, named
    rather than netted off.

    That is not the truncation this replaced. The old rule cut at the first
    breaching DAY and reported the minimum before it as though the days after
    did not exist, so the figure it offered deepened the very month it had
    skipped and said nothing about it. Here the promise stops at a month
    boundary a reader can state, with the deepening reported: the caller
    has both the amount and the gap it does not fix.

    When not even the current month clears the floor there is nothing to
    promise, so the amount is negative and is the sum to be found.

    Raises:
        SustainableError: If the floor is negative, the window is shorter
            than a month or the projection does not include today.
    """
    if floor_pence < 0:
        raise SustainableError("Safety floor cannot be negative")
    within = _window_days(projection, today, window_months)
    covered, beyond = _covered_and_beyond(within, floor_pence)
    worst_beyond = min(beyond, key=lambda d: d.balance_pence) if beyond else None
    if not covered:
        # Today's own month is already under, so there is no promise to make.
        # The figure is THIS month's shortfall rather than the window's
        # deepest point: the nearest gap is the one that can still be acted
        # on. A multi-month depth reported as one number reads as a debt
        # owed today.
        this_month = [
            d for d in within if (d.day.year, d.day.month) == (today.year, today.month)
        ]
        binding = min(this_month, key=lambda d: d.balance_pence)
        rest = within[len(this_month) :]
        worst_rest = min(rest, key=lambda d: d.balance_pence) if rest else None
        return SustainableResult(
            amount_pence=binding.balance_pence - floor_pence,
            binding_day=binding.day,
            covered_end=this_month[-1].day,
            floor_pence=floor_pence,
            shortfall_pence=(
                floor_pence - worst_rest.balance_pence
                if worst_rest and worst_rest.balance_pence - floor_pence < 0
                else 0
            ),
            shortfall_day=(
                worst_rest.day
                if worst_rest and worst_rest.balance_pence - floor_pence < 0
                else None
            ),
        )
    binding = min(covered, key=lambda d: d.balance_pence)
    return SustainableResult(
        amount_pence=binding.balance_pence - floor_pence,
        binding_day=binding.day,
        covered_end=covered[-1].day,
        floor_pence=floor_pence,
        shortfall_pence=(
            floor_pence - worst_beyond.balance_pence if worst_beyond else 0
        ),
        shortfall_day=worst_beyond.day if worst_beyond else None,
    )


def sustainable_capacity(
    *,
    projection: Sequence[DayProjection],
    today: date,
    floor_pence: int = 0,
    window_months: int = _DEFAULT_WINDOW_MONTHS,
) -> tuple[CapacityStep, ...]:
    """`sustainable_spend` from each remaining day of today's month onward.

    Measured over the same covered stretch the headline promises, so the
    first step always equals the headline and no row can offer more than the
    months it names will bear.
    """
    if floor_pence < 0:
        raise SustainableError("Safety floor cannot be negative")
    window = _window_days(projection, today, window_months)
    covered, _ = _covered_and_beyond(window, floor_pence)
    within = covered or window
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
