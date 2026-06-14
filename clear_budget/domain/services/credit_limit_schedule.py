"""Effective credit limit derivation over a card's scheduled limit changes."""

from __future__ import annotations

import calendar
from datetime import date

from clear_budget.domain.entities.credit_card import CreditCard


def effective_credit_limit_pence(*, card: CreditCard, as_of: date) -> int:
    """The card's credit limit effective on `as_of`, in pence.

    Returns the `new_limit` of the latest scheduled change on or before `as_of`,
    falling back to the card's current `credit_limit` when none apply. The
    schedule is sorted by effective date with a stable order, so two changes on
    the same day resolve to the one entered last; the result is always
    well-defined.
    """
    as_of_key = (as_of.year, as_of.month, as_of.day)
    applicable = sorted(
        (c for c in card.scheduled_limit_changes if c.sort_key <= as_of_key),
        key=lambda c: c.sort_key,
    )
    if not applicable:
        return card.credit_limit.pence
    return applicable[-1].new_limit.pence


def month_end_effective_limit_pence(*, card: CreditCard, year: int, month: int) -> int:
    """The card's effective limit at the end of (year, month), in pence."""
    last_day = calendar.monthrange(year, month)[1]
    return effective_credit_limit_pence(card=card, as_of=date(year, month, last_day))
