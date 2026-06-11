"""Balance projection helpers for BudgetService - extracted for LOC limit."""

from typing import Callable

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.domain.services._prorating import (
    days_in_month,
    prorate_remaining_pence,
)
from clear_budget.domain.value_objects.year_month import YearMonth


def _current_month_income_pence(
    summary: MonthSummary, balance_day: int, today_day: int
) -> int:
    if balance_day > 0:
        return sum(
            i.amount.pence
            for i in summary.income_sources
            if i.day_of_month is None or i.day_of_month > balance_day
        )
    return sum(
        i.amount.pence
        for i in summary.income_sources
        if i.day_of_month is None or i.day_of_month >= today_day
    )


def _current_month_bank_bills_pence(summary: MonthSummary, today_day: int) -> int:
    total_days = days_in_month(summary.year_month.year, summary.year_month.month)
    total = 0
    for b in summary.bills:
        if b.payment_method_id != 1:
            continue
        if b.day_of_month is None:
            total += prorate_remaining_pence(b.amount.pence, today_day, total_days)
        elif b.day_of_month >= today_day:
            total += b.amount.pence
    return total


def projected_starting_balance_pence(
    *,
    get_month_summary: Callable[..., MonthSummary],
    get_bank_balance_pence: Callable[[], int],
    get_bank_balance_day: Callable[[], int],
    today_ym: YearMonth,
    today_day: int,
    year_month: YearMonth,
) -> int:
    """Project the bank balance at the start of year_month.

    Accrues forward from today's balance.
    """
    pence = get_bank_balance_pence()
    cursor = today_ym
    while cursor < year_month:
        s = get_month_summary(year_month=cursor)
        if cursor == today_ym:
            balance_day = get_bank_balance_day()
            income = _current_month_income_pence(s, balance_day, today_day)
            bills = _current_month_bank_bills_pence(s, today_day)
        else:
            income = sum(i.amount.pence for i in s.income_sources)
            bills = sum(b.amount.pence for b in s.bills if b.payment_method_id == 1)
        pence += income - bills
        cursor = cursor.next_month()
    return pence


def projected_month_end_balance_pence(
    *,
    get_month_summary: Callable[..., MonthSummary],
    get_bank_balance_pence: Callable[[], int],
    get_bank_balance_day: Callable[[], int],
    today_ym: YearMonth,
    today_day: int,
    year_month: YearMonth,
    summary: MonthSummary,
) -> int:
    """Projected bank balance pence at end of year_month. Signed - can be negative."""
    starting = projected_starting_balance_pence(
        get_month_summary=get_month_summary,
        get_bank_balance_pence=get_bank_balance_pence,
        get_bank_balance_day=get_bank_balance_day,
        today_ym=today_ym,
        today_day=today_day,
        year_month=year_month,
    )
    if year_month == today_ym:
        balance_day = get_bank_balance_day()
        income = _current_month_income_pence(summary, balance_day, today_day)
        bills = _current_month_bank_bills_pence(summary, today_day)
    else:
        income = sum(i.amount.pence for i in summary.income_sources)
        bills = sum(b.amount.pence for b in summary.bills if b.payment_method_id == 1)
    return starting + income - bills
