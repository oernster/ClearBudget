"""Pro-rating helpers for bills with no fixed due date - extracted for reuse."""

import calendar


def days_in_month(year: int, month: int) -> int:
    """Number of days in the given calendar month."""
    return calendar.monthrange(year, month)[1]


def prorate_elapsed_pence(amount_pence: int, today_day: int, days_total: int) -> int:
    """Portion of amount_pence accrued so far this month (days 1..today_day), rounded up."""
    numerator = amount_pence * today_day
    return -(-numerator // days_total)


def prorate_remaining_pence(amount_pence: int, today_day: int, days_total: int) -> int:
    """Portion of amount_pence not yet accrued for the rest of this month."""
    return amount_pence - prorate_elapsed_pence(amount_pence, today_day, days_total)
