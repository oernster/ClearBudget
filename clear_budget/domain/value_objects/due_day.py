"""The day of the month a bill falls due or an income arrives.

One home for the rule, so the dialogs' spin boxes, the table cells and the
entities cannot disagree. A due day is either no day at all or a whole number
from the first day of a month to the last day the longest month has. A day beyond the
length of a particular month (the 31st in April) is still valid; the overnight
update and the projections treat it as that month's last day.
"""

import calendar

from clear_budget.shared.errors import InvalidDueDayError

FIRST_DUE_DAY = 1
# The longest month's length, read from the calendar rather than typed.
LAST_DUE_DAY = max(calendar.mdays)

_REFUSAL = (
    f"A due day is a whole number from {FIRST_DUE_DAY} to {LAST_DUE_DAY}."
    " Leave it empty for no fixed day."
)


def check_due_day(day: int | None) -> None:
    """Refuse anything but None or a day from FIRST_DUE_DAY to LAST_DUE_DAY."""
    if day is None:
        return
    if isinstance(day, bool) or not isinstance(day, int):
        raise InvalidDueDayError(_REFUSAL)
    if not FIRST_DUE_DAY <= day <= LAST_DUE_DAY:
        raise InvalidDueDayError(_REFUSAL)


def due_day_from_text(text: str, *, no_day_mark: str | None = None) -> int | None:
    """Read a typed due day; None for an empty entry.

    `no_day_mark` is what the caller's table prints for "no day", so reading
    back what was printed means no day rather than a refusal. Anything else
    that is not a day in range raises InvalidDueDayError with a message fit
    to show the user.
    """
    cleaned = text.strip()
    if not cleaned or cleaned == no_day_mark:
        return None
    try:
        day = int(cleaned)
    except ValueError:
        raise InvalidDueDayError(_REFUSAL) from None
    check_due_day(day)
    return day


def due_day_from_storage(raw: int | None) -> int | None:
    """A stored day as the rule allows it; repairs rows written before it.

    Each repair matches how the overnight update already treated the value,
    so nothing the user has seen applied changes meaning: a day past the
    longest month fell due on the month's last day; a day below the first
    was never applied, which is what "no fixed day" means.
    """
    if raw is None or raw < FIRST_DUE_DAY:
        return None
    return min(raw, LAST_DUE_DAY)
