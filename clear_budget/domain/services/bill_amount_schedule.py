"""Effective bill amount derivation over a bill's scheduled amount changes.

Mirrors `credit_limit_schedule`, at month granularity rather than day.

THE RULE THIS ENFORCES: a change to a bill never restates history. A change
recorded as effective from a month applies to that month and every month after
it, and to no month before it. An earlier month keeps the amount it actually
had, so a report run for it says what was really paid.
"""

from __future__ import annotations

from clear_budget.domain.entities.bill import Bill


def effective_bill_amount_pence(*, bill: Bill, year: int, month: int) -> int:
    """The bill's amount for (year, month), in pence.

    Returns the `new_amount` of the latest change effective on or before that
    month, falling back to the bill's own `amount` when none apply. Two changes
    recorded for the same month resolve to the one stored last, so the result
    is always well defined rather than dependent on iteration order.
    """
    as_of_key = (year, month)
    applicable = sorted(
        (c for c in bill.amount_changes if c.sort_key <= as_of_key),
        key=lambda c: c.sort_key,
    )
    if not applicable:
        return bill.amount.pence
    return applicable[-1].new_amount.pence
