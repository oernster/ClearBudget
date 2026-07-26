"""Fold elapsed dated bank transactions into the stored balance.

Dated bank bills and income are applied to the bank balance at local
midnight on their due day. Each run folds every dated item that fell due
after the stored balance's baseline date into the balance, marks the item
paid/received so no projection counts it again, then advances the baseline
to today. Run at startup (catching up any days the app was closed) and at
midnight while the app is open.

A due day beyond the length of its month (say the 31st in April) is
treated as due on the last day of that month, so such items are never
silently skipped.
"""

from datetime import date, timedelta

from clear_budget.application.services._balance_application import record_applied
from clear_budget.application.services._settings_operations import (
    get_bank_balance_date_iso,
    get_bank_balance_day,
    get_bank_balance_pence,
    set_bank_balance_pence,
)
from clear_budget.domain.services._prorating import days_in_month
from clear_budget.domain.value_objects.year_month import YearMonth

_BANK_ACCOUNT_ID = 1


def resolve_baseline_date(
    *, iso_value: str | None, balance_day: int, today: date
) -> date | None:
    """Date the stored balance is accurate as-of; None when never set.

    Databases from before the full date was stored carry only a
    day-of-month; that is taken as its most recent occurrence on or
    before today.
    """
    if iso_value:
        return date.fromisoformat(iso_value)
    if balance_day <= 0:
        return None
    if balance_day <= today.day:
        return date(today.year, today.month, balance_day)
    prev = YearMonth(today.year, today.month).previous_month()
    clamped = min(balance_day, days_in_month(prev.year, prev.month))
    return date(prev.year, prev.month, clamped)


def _due_on(day_of_month: int | None, on_day: date) -> bool:
    """Whether an item with this due day falls due on on_day (clamped)."""
    if day_of_month is None:
        return False
    month_days = days_in_month(on_day.year, on_day.month)
    return min(day_of_month, month_days) == on_day.day


def apply_elapsed_bank_transactions(
    *,
    conn,
    get_month_summary,
    mark_bill_paid,
    mark_income_received,
    mark_income_extra_received,
    today: date,
) -> int:
    """Fold elapsed dated bank items into the balance; return the delta pence.

    Skips items already marked paid/received (the balance is presumed to
    reflect them). Only bank-account bills touch the balance; card bills
    are handled by the card fold. Advances the baseline to today even when
    nothing was due, so a same-day item the user declined to apply is
    never applied late.
    """
    if conn is None:
        return 0
    baseline = resolve_baseline_date(
        iso_value=get_bank_balance_date_iso(conn),
        balance_day=get_bank_balance_day(conn),
        today=today,
    )
    if baseline is None or baseline >= today:
        return 0
    delta = 0
    summaries: dict[YearMonth, object] = {}
    day = baseline + timedelta(days=1)
    while day <= today:
        year_month = YearMonth(day.year, day.month)
        if year_month not in summaries:
            summaries[year_month] = get_month_summary(year_month=year_month)
        summary = summaries[year_month]
        for bill in summary.bills:
            if (
                bill.payment_method_id == _BANK_ACCOUNT_ID
                and not bill.paid_for_month
                and _due_on(bill.day_of_month, day)
            ):
                delta -= bill.amount.pence
                mark_bill_paid(bill.id, year_month)
                record_applied(
                    conn,
                    item_type="bill",
                    item_id=bill.id,
                    year_month=year_month,
                    amount_pence=-bill.amount.pence,
                )
        for income in summary.income_sources:
            if income.received_for_month or not _due_on(income.day_of_month, day):
                continue
            delta += income.amount.pence
            if income.is_month_only:
                mark_income_extra_received(income.id)
                income_type = "income_extra"
            else:
                mark_income_received(income.id, year_month)
                income_type = "income"
            record_applied(
                conn,
                item_type=income_type,
                item_id=income.id,
                year_month=year_month,
                amount_pence=income.amount.pence,
            )
        day += timedelta(days=1)
    set_bank_balance_pence(conn, get_bank_balance_pence(conn) + delta, today=today)
    return delta
