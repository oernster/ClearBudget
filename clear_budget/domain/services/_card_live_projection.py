"""Live pro-rated credit card balance projection - extracted for LOC limit."""

import calendar
from datetime import date

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.services._prorating import prorate_elapsed_pence
from clear_budget.domain.value_objects.amount import Amount


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

    balance_pence = (
        opening_balance_pence + accrued_charges_pence - accrued_payments_pence
    )
    return Amount(pence=max(0, balance_pence))
