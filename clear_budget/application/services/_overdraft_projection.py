"""Overdraft-runway projection helper for BudgetService - extracted for LOC limit."""

from typing import Callable

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.domain.services.bank_cashflow import (
    BankCashflowService,
    DailyCashflowEvent,
)
from clear_budget.domain.value_objects.year_month import YearMonth

# Two-year forward limit on the runway search: past this horizon a standing
# deficit is a budgeting decision rather than a dated warning, so we stop looking.
_DEFAULT_HORIZON_MONTHS = 24

# The Bank Account payment method (bills paid straight from the current account).
_BANK_PAYMENT_METHOD_ID = 1
# Day assumptions for undated items, mirroring the cashflow narrative: undated
# income lands at the start of the month, undated bills near its end.
_UNDATED_INCOME_DAY = 1
_UNDATED_BILL_DAY = 28


def _month_events(summary: MonthSummary) -> list[DailyCashflowEvent]:
    """Day-ordered income (positive) and bank-bill (negative) events for a month.

    Income is listed before bills so that, on a shared day, income is received
    before bills are taken (the same optimistic ordering the cashflow uses).
    """
    events = [
        DailyCashflowEvent(inc.day_of_month or _UNDATED_INCOME_DAY, inc.amount.pence)
        for inc in summary.income_sources
    ]
    events += [
        DailyCashflowEvent(bill.day_of_month or _UNDATED_BILL_DAY, -bill.amount.pence)
        for bill in summary.bills
        if bill.payment_method_id == _BANK_PAYMENT_METHOD_ID
    ]
    return events


def first_overdrawn_month(
    *,
    get_month_summary: Callable[..., MonthSummary],
    from_year_month: YearMonth,
    from_balance_pence: int,
    horizon_months: int = _DEFAULT_HORIZON_MONTHS,
) -> YearMonth | None:
    """First month after ``from_year_month`` whose balance dips below zero.

    Projects forward from ``from_balance_pence`` (the projected end-of-month
    balance of ``from_year_month``), simulating each later month day by day. A
    month counts as overdrawn if the balance goes negative at any point during
    it, even when later income lifts it back to a positive close. Returns
    ``None`` when no month dips negative across the horizon.
    """
    balance = from_balance_pence
    cursor = from_year_month
    for _ in range(horizon_months):
        cursor = cursor.next_month()
        summary = get_month_summary(year_month=cursor)
        projection = BankCashflowService.project_month(
            starting_balance_pence=balance,
            events=_month_events(summary),
        )
        if projection.first_negative_day is not None:
            return cursor
        balance = projection.closing_balance_pence
    return None
