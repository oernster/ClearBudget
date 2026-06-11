"""Live card balance + elapsed-date balance update helpers - extracted for LOC limit."""

from datetime import date

from clear_budget.domain.services._card_live_projection import (
    calculate_live_card_balance,
)
from clear_budget.domain.services.card_monthly_calculator import (
    calculate_card_monthly_state,
)
from clear_budget.domain.value_objects.year_month import YearMonth


def get_live_card_balance(payment_method_repo, get_month_summary, *, card, today: date):
    """Return the card's live (pro-rated) balance as of `today`."""
    today_ym = YearMonth(today.year, today.month)
    summary = get_month_summary(year_month=today_ym)
    return calculate_live_card_balance(
        card=card,
        opening_balance_pence=card.current_balance_used.pence,
        bills=list(summary.all_bills),
        today=today,
    )


def update_card_balances_for_elapsed_dates(
    payment_method_repo, get_month_summary, *, today: date
) -> None:
    """Fold the closing balance into each card once its payment date has passed.

    For each active card whose `payment_due_day` has elapsed this month and
    whose stored balance has not yet been updated for this month, persist the
    closing balance for the elapsed month and stamp `balance_applied_year`/
    `balance_applied_month` so the update is not applied again.
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
        summary = get_month_summary(year_month=today_ym)
        state = calculate_card_monthly_state(
            card=card,
            opening_balance_pence=card.current_balance_used.pence,
            bills=list(summary.all_bills),
        )
        payment_method_repo.update_credit_card_balance(
            card_id=card.id, balance_used=state.closing_balance.pence
        )
        payment_method_repo.set_balance_applied(
            card_id=card.id, year=today.year, month=today.month
        )
