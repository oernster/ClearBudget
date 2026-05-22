"""CardMonthlyCalculator - computes per-card monthly charges, payments and interest."""

from dataclasses import dataclass

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount

_MIN_PAYMENT_FLOOR_PENCE = 2500  # £25 minimum floor


@dataclass(frozen=True, slots=True)
class CardMonthlyState:
    """Financial state of a credit card for one month."""

    card: CreditCard
    opening_balance: Amount
    charges: Amount
    payment_received: Amount
    monthly_interest: Amount
    closing_balance: Amount
    minimum_payment: Amount  # max(£25, interest + 1% of balance)
    payment_date: int | None


def calculate_card_monthly_state(
    *,
    card: CreditCard,
    opening_balance_pence: int,
    bills: list[Bill],
) -> CardMonthlyState:
    """Calculate one month's financial state for a card.

    Args:
        card: The credit card entity (contains APR)
        opening_balance_pence: Balance at start of month in pence
        bills: All bills for the month (used to find charges and payments)
    """
    charges_pence = sum(b.amount.pence for b in bills if b.payment_method_id == card.id)
    payment_pence = sum(
        b.amount.pence
        for b in bills
        if b.category == "credit_payment" and b.target_card_id == card.id
    )
    apr = card.interest_rate_apr or 0.0
    monthly_interest_pence = int(opening_balance_pence * apr / 1200)

    closing_pence = (
        opening_balance_pence + charges_pence - payment_pence + monthly_interest_pence
    )

    if opening_balance_pence > 0:
        if card.minimum_payment_pence is not None:
            minimum_pence = card.minimum_payment_pence
        elif card.minimum_payment_percent:
            # Per-card calibrated percentage (no fixed floor - some cards sit below £25)
            minimum_pence = max(
                1, int(opening_balance_pence * card.minimum_payment_percent / 100)
            )
        else:
            # Generic fallback: max(£25, interest + 1% of balance)
            one_percent_pence = int(opening_balance_pence * 0.01)
            minimum_pence = max(
                _MIN_PAYMENT_FLOOR_PENCE, monthly_interest_pence + one_percent_pence
            )
    else:
        minimum_pence = 0

    payment_bill = next(
        (
            b
            for b in bills
            if b.category == "credit_payment" and b.target_card_id == card.id
        ),
        None,
    )

    return CardMonthlyState(
        card=card,
        opening_balance=Amount(pence=opening_balance_pence),
        charges=Amount(pence=charges_pence),
        payment_received=Amount(pence=payment_pence),
        monthly_interest=Amount(pence=monthly_interest_pence),
        closing_balance=Amount(pence=max(0, closing_pence)),
        minimum_payment=Amount(pence=minimum_pence),
        payment_date=payment_bill.day_of_month if payment_bill else None,
    )
