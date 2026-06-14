"""Live card balance + elapsed-date balance update helpers - extracted for LOC limit."""

from dataclasses import replace
from datetime import date

from clear_budget.domain.services._card_live_projection import (
    anchored_month_opening_pence,
    calculate_live_card_balance,
)
from clear_budget.domain.services.card_monthly_calculator import (
    calculate_card_monthly_state,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


def get_live_card_balance(payment_method_repo, get_month_summary, *, card, today: date):
    """Return the card's live (pro-rated) balance as of `today`.

    The opening is derived from the card's anchor (`anchored_month_opening_pence`)
    so a balance set mid-month is honoured: on the day it was set the live
    balance equals exactly that figure, and it then tracks the charges and
    payments that post afterwards.
    """
    today_ym = YearMonth(today.year, today.month)
    bills = list(get_month_summary(year_month=today_ym).all_bills)
    opening_pence = anchored_month_opening_pence(
        card=card, bills=bills, year=today.year, month=today.month
    )
    return calculate_live_card_balance(
        card=card,
        opening_balance_pence=opening_pence,
        bills=bills,
        today=today,
    )


def save_card_with_today_balance(
    payment_method_repo,
    *,
    card,
    today_balance_pence: int,
    today: date,
    is_new: bool,
) -> int:
    """Persist a card from the balance the user entered as of `today`.

    The entered figure is stored verbatim as `current_balance_used` and stamped
    with today's date as its anchor (`balance_applied_*`). "Current Balance" and
    "Used" are therefore the same number: what the user typed. The projection
    layer derives the start-of-month opening it needs on the fly from this anchor
    (see `anchored_month_opening_pence`); nothing is transformed at rest. The
    same-month stamp also makes the elapsed-date fold skip this card, so a freshly
    entered balance is never overwritten. Returns the persisted card id.
    """
    stored = replace(
        card,
        current_balance_used=Amount(pence=today_balance_pence),
        balance_applied_year=today.year,
        balance_applied_month=today.month,
        balance_applied_day=today.day,
    )
    if is_new:
        card_id = payment_method_repo.add_credit_card(card=stored).id
    else:
        payment_method_repo.update_credit_card(card=stored)
        card_id = stored.id
    payment_method_repo.set_balance_applied(
        card_id=card_id, year=today.year, month=today.month, day=today.day
    )
    return card_id


def update_card_balances_for_elapsed_dates(
    payment_method_repo, get_month_summary, *, today: date
) -> None:
    """Fold the closing balance into each card once its payment date has passed.

    For each active card whose `payment_due_day` has elapsed this month and
    whose stored balance has not yet been updated for this month, persist the
    closing balance for the month and stamp `balance_applied_year`/
    `balance_applied_month` (no day anchor) so the update is not applied again.
    A card whose balance was set manually this month is already stamped for this
    month and is therefore skipped, never overwritten.
    """
    today_ym = YearMonth(today.year, today.month)
    cards = payment_method_repo.get_all_credit_cards(include_inactive=False)
    for card in cards:
        if today.day < card.payment_due_day:
            continue
        if (card.balance_applied_year, card.balance_applied_month) == (
            today.year,
            today.month,
        ):
            continue
        bills = list(get_month_summary(year_month=today_ym).all_bills)
        opening_pence = anchored_month_opening_pence(
            card=card, bills=bills, year=today.year, month=today.month
        )
        state = calculate_card_monthly_state(
            card=card,
            opening_balance_pence=opening_pence,
            bills=bills,
        )
        payment_method_repo.update_credit_card_balance(
            card_id=card.id, balance_used=state.closing_balance.pence
        )
        payment_method_repo.set_balance_applied(
            card_id=card.id, year=today.year, month=today.month
        )
