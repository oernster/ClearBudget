"""Tests for the live pro-rated credit card balance projection."""

from datetime import date

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.services._card_live_projection import (
    calculate_live_card_balance,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


def _card(card_id: int = 2, balance_pence: int = 10000) -> CreditCard:
    return CreditCard(
        id=card_id,
        name="TestCard",
        credit_limit=Amount(pence=100000),
        current_balance_used=Amount(pence=balance_pence),
        payment_due_day=22,
    )


def _bill(
    *,
    pence: int,
    payment_method_id: int = 1,
    category: str = "groceries",
    target_card_id: int | None = None,
    day: int | None = None,
) -> Bill:
    return Bill(
        id=1,
        name="Test bill",
        amount=Amount(pence=pence),
        payment_method_id=payment_method_id,
        category=category,
        bill_type="fixed",
        day_of_month=day,
        start_ym=YearMonth(2000, 1),
        end_ym=None,
        active=True,
        target_card_id=target_card_id,
    )


class TestCalculateLiveCardBalance:
    def test_dated_charge_already_due_counts_fully(self) -> None:
        card = _card()
        bills = [_bill(pence=1500, payment_method_id=card.id, day=10)]
        result = calculate_live_card_balance(
            card=card,
            opening_balance_pence=10000,
            bills=bills,
            today=date(2026, 6, 15),
        )
        assert result.pence == 11500

    def test_dated_charge_not_yet_due_excluded(self) -> None:
        card = _card()
        bills = [_bill(pence=1500, payment_method_id=card.id, day=20)]
        result = calculate_live_card_balance(
            card=card,
            opening_balance_pence=10000,
            bills=bills,
            today=date(2026, 6, 15),
        )
        assert result.pence == 10000

    def test_undated_charge_pro_rated_by_elapsed_days(self) -> None:
        card = _card()
        # June has 30 days; halfway through (day 15) -> half of 3000 = 1500
        bills = [_bill(pence=3000, payment_method_id=card.id, day=None)]
        result = calculate_live_card_balance(
            card=card,
            opening_balance_pence=0,
            bills=bills,
            today=date(2026, 6, 15),
        )
        assert result.pence == 1500

    def test_credit_payment_to_card_reduces_balance(self) -> None:
        card = _card()
        bills = [
            _bill(
                pence=5000,
                payment_method_id=1,
                category="credit_payment",
                target_card_id=card.id,
                day=5,
            )
        ]
        result = calculate_live_card_balance(
            card=card,
            opening_balance_pence=10000,
            bills=bills,
            today=date(2026, 6, 15),
        )
        assert result.pence == 5000

    def test_other_card_charges_ignored(self) -> None:
        card = _card(card_id=2)
        bills = [_bill(pence=1500, payment_method_id=99, day=1)]
        result = calculate_live_card_balance(
            card=card,
            opening_balance_pence=10000,
            bills=bills,
            today=date(2026, 6, 15),
        )
        assert result.pence == 10000

    def test_balance_floors_at_zero(self) -> None:
        card = _card()
        bills = [
            _bill(
                pence=20000,
                payment_method_id=1,
                category="credit_payment",
                target_card_id=card.id,
                day=1,
            )
        ]
        result = calculate_live_card_balance(
            card=card,
            opening_balance_pence=10000,
            bills=bills,
            today=date(2026, 6, 15),
        )
        assert result.pence == 0

    def test_leap_year_february_pro_rates_correctly(self) -> None:
        card = _card()
        # 2028 is a leap year, Feb has 29 days; day 29 -> full amount
        bills = [_bill(pence=2900, payment_method_id=card.id, day=None)]
        result = calculate_live_card_balance(
            card=card,
            opening_balance_pence=0,
            bills=bills,
            today=date(2028, 2, 29),
        )
        assert result.pence == 2900
