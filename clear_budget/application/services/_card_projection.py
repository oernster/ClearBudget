"""Card projection helpers - extracted from BudgetService to stay under LOC limit."""

from datetime import datetime

from clear_budget.domain.services._card_live_projection import (
    anchored_month_opening_pence,
)
from clear_budget.domain.services.card_monthly_calculator import (
    calculate_card_monthly_state,
)
from clear_budget.domain.value_objects.year_month import YearMonth


def get_card_monthly_states(
    payment_method_repo, get_month_summary, year_month: YearMonth
) -> list:  # pragma: no cover
    """Return CardMonthlyState for each active card for year_month."""
    cards = payment_method_repo.get_all_credit_cards(include_inactive=False)
    summary = get_month_summary(year_month=year_month)
    all_bills = list(summary.all_bills)
    today_ym = YearMonth(datetime.now().year, datetime.now().month)
    today_bills = list(get_month_summary(year_month=today_ym).all_bills)
    results = []
    for card in cards:
        balance_pence = anchored_month_opening_pence(
            card=card, bills=today_bills, year=today_ym.year, month=today_ym.month
        )
        cursor = today_ym
        while cursor < year_month:
            s = get_month_summary(year_month=cursor)
            interim = calculate_card_monthly_state(
                card=card,
                opening_balance_pence=balance_pence,
                bills=list(s.all_bills),
            )
            balance_pence = interim.closing_balance.pence
            cursor = cursor.next_month()
        results.append(
            calculate_card_monthly_state(
                card=card, opening_balance_pence=balance_pence, bills=all_bills
            )
        )
    return results


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
    today_ym = YearMonth(datetime.now().year, datetime.now().month)
    today_bills = list(get_month_summary(year_month=today_ym).all_bills)
    balances = {
        card.id: anchored_month_opening_pence(
            card=card, bills=today_bills, year=today_ym.year, month=today_ym.month
        )
        for card in cards
    }
    cursor = today_ym
    while cursor < start_month:
        s = get_month_summary(year_month=cursor)
        bills = list(s.all_bills)
        for card in cards:
            state = calculate_card_monthly_state(
                card=card, opening_balance_pence=balances[card.id], bills=bills
            )
            balances[card.id] = state.closing_balance.pence
        cursor = cursor.next_month()
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
