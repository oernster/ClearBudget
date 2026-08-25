"""One month simulated day by day: the numeric core, told by nobody.

Lifted out of the Solvency panel, where it had grown up as UI code although
nothing about it is UI: it is projection arithmetic over a month's own items.
Two pages now need it. The bank page tells a month's story from it and the
Reserves page reads the same months against what they hold back.

That is the whole reason it moved. The two pages must agree about a month's
low and the day it lands on; the only way to be sure of that is for there to
be ONE walk. Two correct-looking simulations that disagree about the same
month is precisely the failure the brief's invariant is written to forbid.

No Qt, no I/O and no clock: the caller supplies the opening balance and the
month's summary, so the same inputs always give the same answer.
"""

from __future__ import annotations

# The low sits at the opening until some item moves the balance below it, so
# day zero means "before anything happened" rather than a real day.
LOW_AT_START = 0

_BANK_PAYMENT_METHOD_ID = 1
# Where an item with no day of its own is placed. Income lands at the start of
# the month and a bill at the end, which is the cautious reading: it assumes
# the money arrives no earlier and leaves no later than it might.
_UNDATED_INCOME_DAY = 1
_UNDATED_BILL_DAY = 28


def walk_month(opening_pence: int, summary) -> dict:
    """Simulate one month day by day and report what it did.

    Returns the low and the day it fell on, the first day the balance went
    below zero, the income that rescued it if one did, then where the month
    closed.

    Income is applied before bills on a shared day, which is the same
    optimistic ordering the bank projection uses: money is received before
    payments are taken.
    """
    events = []
    for inc in summary.income_sources:
        events.append(
            (inc.day_of_month or _UNDATED_INCOME_DAY, inc.amount.pence, inc.name)
        )
    for bill in summary.bills:
        if bill.payment_method_id == _BANK_PAYMENT_METHOD_ID:
            events.append(
                (
                    bill.day_of_month or _UNDATED_BILL_DAY,
                    -bill.amount.pence,
                    bill.name,
                )
            )
    # Income before bills on same day (positive delta sorts first)
    events.sort(key=lambda e: (e[0], -e[1]))

    balance = opening_pence
    min_balance = opening_pence
    min_day = LOW_AT_START
    first_negative_day = None
    rescue_event = None
    for day, delta, name in events:
        balance += delta
        if balance < min_balance:
            min_balance = balance
            min_day = day
        if balance < 0 and first_negative_day is None:
            first_negative_day = day
        if (
            first_negative_day is not None
            and rescue_event is None
            and delta > 0
            and balance >= 0
        ):
            rescue_event = (day, delta, name)
    return {
        "min_balance": min_balance,
        "min_day": min_day,
        "first_negative_day": first_negative_day,
        "rescue_event": rescue_event,
        "closing": balance,
    }
