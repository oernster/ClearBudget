"""What a forward projection is allowed to assume about income.

The app shows two readings side by side. The known one counts only money the
user has actually entered and marked reliable, so nothing is quietly propped
up. The second one states an assumption; which assumption it states is this
enum's whole job.

`REPEAT_CURRENT` is the honest one for a budget kept month by month. Later
months look poorer than they are simply because their ad hoc income has not
been entered yet, so a reading that only counts what is typed in reports a
shortfall the user does not have. Repeating this month's income forward says
what the picture looks like if the months ahead resemble this one.

The alternative it replaced keyed off a per-item "reliable" tick, which meant
the second reading stayed invisible until the user thought to mark something.
An assumption nobody remembers to switch on is not a second reading.
"""

from enum import Enum


class ProjectionBasis(Enum):
    """The assumption a forward projection is built on."""

    # Only income entered and marked reliable, month by month, as typed.
    KNOWN = "known"

    # Every income entered for the current month is assumed to arrive, then
    # to arrive again in each later month that has no entry of that name.
    REPEAT_CURRENT = "repeat_current"
