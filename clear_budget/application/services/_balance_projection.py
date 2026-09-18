"""Balance projection helpers for BudgetService - extracted for LOC limit.

Also the ONE home of what the current month still has to come after the
stored balance. The balance carried into next month and the Solvency report
both need that answer; each once kept its own copy of the rule, so fixing one
left the other counting Received income twice.
"""

from collections.abc import Callable
from dataclasses import replace

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.domain.services._prorating import (
    days_in_month,
    prorate_remaining_pence,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth

_BANK_PAYMENT_METHOD_ID = 1


def pending_income(income, balance_day: int, today_day: int) -> tuple:
    """Income this month still to arrive in the bank after the stored balance.

    Income marked Received is already inside the stored balance, whatever its
    due day, exactly as a Paid bill is already out of it; counting it again
    would open next month too high by its amount. With a balance day stored,
    income due on or before it is presumed inside the typed figure; without
    one, today decides.
    """
    pending = (i for i in income if not i.received_for_month)
    if balance_day > 0:
        return tuple(
            i for i in pending if i.day_of_month is None or i.day_of_month > balance_day
        )
    return tuple(
        i for i in pending if i.day_of_month is None or i.day_of_month >= today_day
    )


def pending_bills(bills, today_day: int, total_days: int) -> tuple:
    """Bills this month still to leave, whatever pays them.

    A Paid bill is already out of the stored balance. An undated one is
    reduced to the share of the month still to run, since part of it is
    presumed spent already.
    """
    return tuple(
        (
            replace(
                b,
                amount=Amount(
                    pence=prorate_remaining_pence(b.amount.pence, today_day, total_days)
                ),
            )
            if b.day_of_month is None
            else b
        )
        for b in bills
        if not b.paid_for_month
        and (b.day_of_month is None or b.day_of_month >= today_day)
    )


def _current_month_income_pence(
    summary: MonthSummary, balance_day: int, today_day: int
) -> int:
    income = pending_income(summary.income_sources, balance_day, today_day)
    return sum(i.amount.pence for i in income)


def _current_month_bank_bills_pence(summary: MonthSummary, today_day: int) -> int:
    total_days = days_in_month(summary.year_month.year, summary.year_month.month)
    return sum(
        b.amount.pence
        for b in pending_bills(summary.bills, today_day, total_days)
        if b.payment_method_id == _BANK_PAYMENT_METHOD_ID
    )


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
