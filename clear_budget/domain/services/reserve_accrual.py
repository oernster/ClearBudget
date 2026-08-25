"""Reserve accrual  -  what a commitment is holding back on a given day.

Pure: dates and commitments in, pence out. No clock is read here, so the
answer is decided by the arguments rather than by the day the code runs.

The accrual is deliberately over the months REMAINING rather than over the
commitment's natural period. An annual bill entered four months before it
lands accrues at a quarter of it a month, not a twelfth: the money genuinely
has to be found in four months; a gentler figure would be a reassurance
the calendar does not support. The natural rate is reported alongside it so
the first steep cycle can be explained rather than just endured.

Two functions rather than one, because the due day has to say two things at
once. `accrued_pence` is the ramp: it climbs from what is already held to the
full amount and reaches it exactly on the due date. `reserve_pence` is that
ramp with the drop applied, because on the day the money leaves the account
it is no longer being held back. The pair is what makes the netting-out in
the projection fall out of the maths rather than needing a special case.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from clear_budget.domain.entities.commitment import Commitment
from clear_budget.domain.value_objects.recurrence import MONTHS_IN_YEAR


@dataclass(frozen=True, slots=True)
class Occurrence:
    """The cycle a given day falls inside.

    Attributes:
        accrual_start: The day this cycle began accruing from
        due: The day this occurrence falls due
        held_pence: What was already put by for THIS occurrence; zero for
            every cycle after the first, since a new cycle starts empty
    """

    accrual_start: date
    due: date
    held_pence: int


def add_months(day: date, months: int) -> date:
    """`day` moved by `months`, clamped to the last day of a short month.

    A commitment due on the 31st falls on the 30th in a 30-day month, which
    is the rule bills already follow for their due day.
    """
    total = (day.year * MONTHS_IN_YEAR) + (day.month - 1) + months
    year, month = divmod(total, MONTHS_IN_YEAR)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _still_running(due: date, day: date, closing: bool) -> bool:
    """Whether the cycle ending at `due` still contains `day`.

    The due day belongs to the cycle it CLOSES when the caller is asking what
    was accrued; it belongs to the cycle it OPENS when the caller asks what is
    held back. One comparison decides both readings, so the two can never
    drift apart.
    """
    return day < due or (closing and day == due)


def occurrence_at(
    commitment: Commitment, day: date, *, closing: bool = False
) -> Occurrence | None:
    """The cycle `day` sits in; None when nothing is being reserved for.

    None covers three cases that all mean the same thing to a caller: the
    commitment has not started yet, it has been ended, it was a one-off
    whose day has passed.
    """
    if not commitment.applies_on(day):
        return None
    start = commitment.created_month.first_day()
    due = commitment.due_date
    if _still_running(due, day, closing):
        return Occurrence(
            accrual_start=min(start, due),
            due=due,
            held_pence=commitment.already_held.pence,
        )
    interval = commitment.recurrence.months
    if interval is None:
        return None
    # Roll forward to the cycle containing `day`. Each new cycle accrues from
    # the previous occurrence's due date and starts empty, since whatever was
    # held went out with the payment.
    previous = due
    following = add_months(due, interval)
    while not _still_running(following, day, closing):
        previous = following
        following = add_months(following, interval)
    return Occurrence(accrual_start=previous, due=following, held_pence=0)


def accrued_pence(commitment: Commitment, day: date) -> int:
    """The ramp: what has been put by for the current cycle by `day`.

    Climbs from what was already held to the full amount, reaching it exactly
    on the due date. Integer arithmetic throughout, so the figure a user reads
    is the figure the projection used.
    """
    occurrence = occurrence_at(commitment, day, closing=True)
    if occurrence is None:
        return 0
    return _ramp_pence(commitment, occurrence, day)


def reserve_pence(commitment: Commitment, day: date) -> int:
    """What `commitment` holds back from the balance on `day`.

    The ramp until the due date, then nothing. No special case is needed for
    the day itself: that day opens the next cycle, which has accrued nothing
    yet, so the reserve falls to zero exactly as the money leaves.
    """
    occurrence = occurrence_at(commitment, day)
    if occurrence is None:
        return 0
    return _ramp_pence(commitment, occurrence, day)


def _ramp_pence(commitment: Commitment, occurrence: Occurrence, day: date) -> int:
    """`occurrence`'s accrual evaluated at `day`, capped at the full amount."""
    amount = commitment.amount.pence
    held = min(occurrence.held_pence, amount)
    outstanding = max(amount - held, 0)
    span = (occurrence.due - occurrence.accrual_start).days
    if span <= 0:
        # The window closed before it opened: entered on or after its own due
        # date, so the whole amount is owed at once rather than smoothed.
        return amount
    elapsed = min(max((day - occurrence.accrual_start).days, 0), span)
    return held + (outstanding * elapsed) // span


def months_remaining(commitment: Commitment, day: date) -> int:
    """Whole months from `day` to the due date, at least one.

    At least one because a commitment due this month still has to be found
    this month; reporting zero months would divide the rate by nothing.
    """
    occurrence = occurrence_at(commitment, day)
    if occurrence is None:
        return 1
    months = (occurrence.due.year - day.year) * MONTHS_IN_YEAR
    months += occurrence.due.month - day.month
    return max(months, 1)


def monthly_rate_pence(commitment: Commitment, day: date) -> int:
    """What has to be found each month from `day` to reach the due date.

    Rounded UP: a rate that rounds down leaves a shortfall on the due day,
    which is the one day the figure exists to prevent.
    """
    occurrence = occurrence_at(commitment, day)
    if occurrence is None:
        return 0
    held = min(occurrence.held_pence, commitment.amount.pence)
    outstanding = max(commitment.amount.pence - held, 0)
    months = months_remaining(commitment, day)
    return -(-outstanding // months)


def natural_rate_pence(commitment: Commitment) -> int:
    """What the same commitment settles at once a full cycle is available.

    The figure that explains a steep first cycle: an annual bill entered four
    months out costs a quarter of itself a month now and a twelfth of itself
    every year after.
    """
    interval = commitment.recurrence.months
    if interval is None:
        return commitment.amount.pence
    return -(-commitment.amount.pence // interval)
