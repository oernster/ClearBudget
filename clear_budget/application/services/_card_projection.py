"""Card projection helpers - extracted from BudgetService to stay under LOC limit."""

from datetime import datetime

from clear_budget.domain.services._card_live_projection import (
    anchored_month_opening_pence,
)
from clear_budget.domain.services.card_monthly_calculator import (
    calculate_card_monthly_state,
)
from clear_budget.domain.value_objects.year_month import YearMonth


def card_openings_at(
    payment_method_repo, get_month_summary, *, month: YearMonth, today_ym: YearMonth
) -> dict[int, int]:
    """Opening balance per active card at the start of ``month``, in pence.

    Chains calculate_card_monthly_state month by month from today's anchored
    opening, so the per-card panels, the projection strip and the month graph
    all start a month from the SAME figure. Reading the stored balance for a
    future month instead is the bug this exists to prevent: the stored figure
    is as-of the day it was entered, so a month years ahead opened as though
    no intervening payment or interest had ever happened. A month at or
    before the current one returns the anchored opening unchained, since
    there is nothing recorded to chain it from.
    """
    cards = payment_method_repo.get_all_credit_cards(include_inactive=False)
    today_bills = list(get_month_summary(year_month=today_ym).all_bills)
    balances = {
        card.id: anchored_month_opening_pence(
            card=card, bills=today_bills, year=today_ym.year, month=today_ym.month
        )
        for card in cards
    }
    cursor = today_ym
    while cursor < month:
        bills = list(get_month_summary(year_month=cursor).all_bills)
        for card in cards:
            state = calculate_card_monthly_state(
                card=card, opening_balance_pence=balances[card.id], bills=bills
            )
            balances[card.id] = state.closing_balance.pence
        cursor = cursor.next_month()
    return balances


def get_card_monthly_states(
    payment_method_repo, get_month_summary, year_month: YearMonth
) -> list:  # pragma: no cover
    """Return CardMonthlyState for each active card for year_month."""
    cards = payment_method_repo.get_all_credit_cards(include_inactive=False)
    now = datetime.now()  # noqa: DTZ005 (app runs on naive local time)
    balances = card_openings_at(
        payment_method_repo,
        get_month_summary,
        month=year_month,
        today_ym=YearMonth(now.year, now.month),
    )
    all_bills = list(get_month_summary(year_month=year_month).all_bills)
    return [
        calculate_card_monthly_state(
            card=card, opening_balance_pence=balances[card.id], bills=all_bills
        )
        for card in cards
    ]


def get_card_projection_months(
    payment_method_repo,
    get_month_summary,
    *,
    start_month: YearMonth,
    n_months: int,
) -> list[list]:  # pragma: no cover
    """Return n_months of CardMonthlyState lists starting from start_month.

    Each element is a list of CardMonthlyState (one per active card).
    Balances chain forward correctly.
    """
    cards = payment_method_repo.get_all_credit_cards(include_inactive=False)
    now = datetime.now()  # noqa: DTZ005 (app runs on naive local time)
    balances = card_openings_at(
        payment_method_repo,
        get_month_summary,
        month=start_month,
        today_ym=YearMonth(now.year, now.month),
    )
    results = []
    cursor = start_month
    for _ in range(n_months):
        s = get_month_summary(year_month=cursor)
        bills = list(s.all_bills)
        month_states = []
        for card in cards:
            state = calculate_card_monthly_state(
                card=card, opening_balance_pence=balances[card.id], bills=bills
            )
            balances[card.id] = state.closing_balance.pence
            month_states.append(state)
        results.append(month_states)
        cursor = cursor.next_month()
    return results
