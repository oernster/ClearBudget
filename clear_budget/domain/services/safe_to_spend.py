"""Safe to Spend Today - pure domain calculation over a day-by-day projection.

The single actionable number the forecasting engine produces: the maximum
amount that could be spent today without any projected day within the horizon
dropping below the configured safety floor.

    safe_to_spend_today = min(P(d) for d in H) - F

where P(d) is the projected end-of-day balance assuming no discretionary
spend today, H is the horizon (today through the day before the next income
event, or the whole forecast window) and F is the safety floor.

The result is signed: a negative value is the shortfall and is NOT clamped
here. Presentation of a shortfall is the UI's job.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from clear_budget.shared.errors import BudgetError


class SafeToSpendError(BudgetError):
    """Raised when a safe-to-spend calculation is given unusable inputs."""


class HorizonStrategy(Enum):
    """How far ahead the safe-to-spend minimum looks."""

    UNTIL_NEXT_INCOME = "until_next_income"
    FULL_FORECAST = "full_forecast"


@dataclass(frozen=True, slots=True)
class DayProjection:
    """Projected end-of-day bank balance for one calendar day."""

    day: date
    balance_pence: int


@dataclass(frozen=True, slots=True)
class SafeToSpendResult:
    """Outcome of a safe-to-spend calculation.

    Attributes:
        amount_pence: Signed safe-to-spend value; negative is the shortfall.
        binding_day: The minimum-balance day that determined the result.
        horizon_end: The last day considered.
        floor_pence: The safety floor the amount was measured against.
        first_breach_day: The first day the projection sits below the floor
            within the horizon, or None when it never does. This is when
            trouble STARTS; binding_day is when it is at its worst. The two
            differ in a budget that erodes month on month, where the deepest
            dip sits at the far end of the window but the first breach may be
            weeks away.
    """

    amount_pence: int
    binding_day: date
    horizon_end: date
    floor_pence: int
    first_breach_day: date | None


def safe_to_spend(
    *,
    projection: Sequence[DayProjection],
    today: date,
    income_days: Sequence[date] = (),
    floor_pence: int = 0,
    horizon: HorizonStrategy = HorizonStrategy.FULL_FORECAST,
) -> SafeToSpendResult:
    """The most that could be spent today without breaching the floor.

    Args:
        projection: Per-day projected end-of-day balances, covering today.
            Days before today are ignored; the sequence need not be sorted.
        today: The day the spend would happen. Injected, never read from
            the clock, so the calculation is deterministic.
        income_days: Dates of projected income events. Only dates strictly
            after today matter: income landing today is already inside
            P(today) and does not end the horizon.
        floor_pence: Safety floor the balance must not drop below.
        horizon: FULL_FORECAST (the default) uses the whole projection, so
            the answer holds for every future day the forecast covers: money
            spent today lowers every later day, so a horizon that stops at
            the next payday overstates safety whenever a later month does not
            pay for itself. UNTIL_NEXT_INCOME ends the horizon the day before
            the next income event (degrading to the full window when no
            future income exists), for those who budget payday to payday.

    Returns:
        SafeToSpendResult with the signed amount and the binding day.

    Raises:
        SafeToSpendError: If the floor is negative or the projection does
            not include today.
    """
    if floor_pence < 0:
        raise SafeToSpendError("Safety floor cannot be negative")

    future = sorted((d for d in projection if d.day >= today), key=lambda d: d.day)
    if not future or future[0].day != today:
        raise SafeToSpendError("Projection must include today")

    horizon_end = future[-1].day
    if horizon is HorizonStrategy.UNTIL_NEXT_INCOME:
        upcoming = sorted(d for d in income_days if d > today)
        if upcoming:
            horizon_end = min(horizon_end, upcoming[0] - timedelta(days=1))

    in_horizon = [d for d in future if d.day <= horizon_end]
    binding = min(in_horizon, key=lambda d: d.balance_pence)
    first_breach = next(
        (d.day for d in in_horizon if d.balance_pence < floor_pence), None
    )
    return SafeToSpendResult(
        amount_pence=binding.balance_pence - floor_pence,
        binding_day=binding.day,
        horizon_end=horizon_end,
        floor_pence=floor_pence,
        first_breach_day=first_breach,
    )
