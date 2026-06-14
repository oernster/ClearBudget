"""Live pro-rated credit card balance projection - extracted for LOC limit."""

import calendar
from datetime import date

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.services._prorating import prorate_elapsed_pence
from clear_budget.domain.value_objects.amount import Amount


def month_to_date_net_pence(
    *,
    card: CreditCard,
    bills: list[Bill],
    today: date,
) -> int:
    """Signed month-to-date movement on the card as of `today`, in pence.

    Returns the charges already posted minus the payments already made this
    month. Dated bills count fully once their day has passed (`<= today.day`);
    undated bills accrue evenly across the days of the month that have elapsed.
    The result is negative when payments so far exceed charges so far.
    """
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    accrued_charges_pence = 0
    accrued_payments_pence = 0

    for bill in bills:
        if bill.day_of_month is not None:
            if bill.day_of_month > today.day:
                continue
            amount_pence = bill.amount.pence
        else:
            amount_pence = prorate_elapsed_pence(
                bill.amount.pence, today.day, days_in_month
            )

        if bill.payment_method_id == card.id:
            accrued_charges_pence += amount_pence
        elif bill.category == "credit_payment" and bill.target_card_id == card.id:
            accrued_payments_pence += amount_pence

    return accrued_charges_pence - accrued_payments_pence


def calculate_live_card_balance(
    *,
    card: CreditCard,
    opening_balance_pence: int,
    bills: list[Bill],
    today: date,
) -> Amount:
    """Calculate a card's live balance as of `today`, pro-rating undated bills.

    Bills with a `day_of_month` count fully once that day has passed (`<=
    today.day`). Bills with `day_of_month is None` accrue evenly across the
    month, based on how many of the month's days have elapsed.
    """
    net_pence = month_to_date_net_pence(card=card, bills=bills, today=today)
    return Amount(pence=max(0, opening_balance_pence + net_pence))


def anchored_month_opening_pence(
    *, card: CreditCard, bills: list[Bill], year: int, month: int
) -> int:
    """Start-of-month opening balance for (year, month), in pence.

    `current_balance_used` holds the figure the user entered, which is their
    balance as of the day they set it (`balance_applied_day`). That figure
    already contains the charges and payments posted between the 1st and that
    day, so when this month needs a start-of-month opening to project from, the
    pre-anchor movement is backed out. For any other month, or for a card with
    no manual anchor day (the balance was folded at a month rollover, or is
    legacy data), the stored figure is already a start-of-month opening and is
    returned unchanged.
    """
    anchor_day = card.balance_applied_day
    is_anchor_month = (
        anchor_day is not None
        and card.balance_applied_year == year
        and card.balance_applied_month == month
    )
    if not is_anchor_month:
        return card.current_balance_used.pence
    pre_anchor_net = month_to_date_net_pence(
        card=card, bills=bills, today=date(year, month, anchor_day)
    )
    return card.current_balance_used.pence - pre_anchor_net
