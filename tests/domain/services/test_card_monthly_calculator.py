"""Tests for CardMonthlyCalculator domain service."""

import pytest

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.services.card_monthly_calculator import (
    CardMonthlyState,
    calculate_card_monthly_state,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


def _card(
    apr: float | None = 24.9, balance_pence: int = 10000, min_pct: float | None = None
) -> CreditCard:
    return CreditCard(
        id=2,
        name="TestCard",
        credit_limit=Amount(pence=100000),
        current_balance_used=Amount(pence=balance_pence),
        interest_rate_apr=apr,
        payment_due_day=22,
        minimum_payment_percent=min_pct,
    )


def _bill(
    *,
    name: str,
    pence: int,
    payment_method_id: int = 1,
    category: str = "groceries",
    target_card_id: int | None = None,
    day: int | None = None,
) -> Bill:
    return Bill(
        id=1,
        name=name,
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


class TestCalculateCardMonthlyState:
    def test_charges_on_card(self) -> None:
        card = _card(apr=0.0, balance_pence=5000)
        bills = [_bill(name="Netflix", pence=1299, payment_method_id=card.id)]
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=5000, bills=bills
        )
        assert state.charges.pence == 1299

    def test_payment_received(self) -> None:
        card = _card(apr=0.0, balance_pence=10000)
        bills = [
            _bill(
                name="Card Pmt",
                pence=5000,
                category="credit_payment",
                target_card_id=card.id,
            )
        ]
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=10000, bills=bills
        )
        assert state.payment_received.pence == 5000

    def test_monthly_interest_zero_apr(self) -> None:
        card = _card(apr=0.0, balance_pence=10000)
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=10000, bills=[]
        )
        assert state.monthly_interest.pence == 0

    def test_monthly_interest_calculated_from_apr(self) -> None:
        # APR=12% → monthly rate=1% → 10000 * 0.01 = 100 pence
        card = _card(apr=12.0, balance_pence=10000)
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=10000, bills=[]
        )
        assert state.monthly_interest.pence == 100

    def test_monthly_interest_none_apr_treated_as_zero(self) -> None:
        card = _card(apr=None, balance_pence=10000)
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=10000, bills=[]
        )
        assert state.monthly_interest.pence == 0

    def test_closing_balance(self) -> None:
        # opening=10000, charges=2000, payment=3000, interest=0 → closing=9000
        card = _card(apr=0.0, balance_pence=10000)
        bills = [
            _bill(name="Charge", pence=2000, payment_method_id=card.id),
            _bill(
                name="Pmt",
                pence=3000,
                category="credit_payment",
                target_card_id=card.id,
            ),
        ]
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=10000, bills=bills
        )
        assert state.closing_balance.pence == 9000

    def test_closing_balance_floored_at_zero(self) -> None:
        card = _card(apr=0.0, balance_pence=0)
        bills = [
            _bill(
                name="Overpay",
                pence=9999,
                category="credit_payment",
                target_card_id=card.id,
            )
        ]
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=0, bills=bills
        )
        assert state.closing_balance.pence == 0

    def test_payment_date_extracted_from_bill(self) -> None:
        card = _card(apr=0.0)
        bills = [
            _bill(
                name="Pmt",
                pence=500,
                category="credit_payment",
                target_card_id=card.id,
                day=22,
            )
        ]
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=5000, bills=bills
        )
        assert state.payment_date == 22

    def test_payment_date_none_when_no_payment_bill(self) -> None:
        card = _card(apr=0.0)
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=5000, bills=[]
        )
        assert state.payment_date is None

    def test_minimum_payment_floor_25(self) -> None:
        # Low balance: 1% + interest < £25 → floor applies
        card = _card(apr=0.0, balance_pence=100)  # 1% = 1p, interest = 0 → floor £25
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=100, bills=[]
        )
        assert state.minimum_payment.pence == 2500  # £25

    def test_minimum_payment_interest_plus_1_percent(self) -> None:
        # APR=12% on £1000 → monthly interest=100p, 1% of £1000=100p → total=200p < £25 → floor
        # Use larger balance so interest+1% > £25
        # APR=12% on £200000 → monthly=2000p, 1%=2000p → total=4000p > £25
        card = _card(apr=12.0, balance_pence=200000)
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=200000, bills=[]
        )
        assert state.minimum_payment.pence == 4000  # 2000 interest + 2000 one-percent

    def test_minimum_payment_zero_when_balance_zero(self) -> None:
        card = _card(apr=24.9, balance_pence=0)
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=0, bills=[]
        )
        assert state.minimum_payment.pence == 0

    def test_minimum_payment_uses_per_card_percent_when_set(self) -> None:
        # Vanquis scenario: 1.45% of £1126.98 ≈ £16.34 (16342 pence)
        card = _card(apr=39.9, balance_pence=112698, min_pct=1.45)
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=112698, bills=[]
        )
        assert state.minimum_payment.pence == int(112698 * 1.45 / 100)

    def test_minimum_payment_per_card_pct_ignores_25_floor(self) -> None:
        # Per-card pct can produce amounts below £25 (e.g. Vanquis behaviour)
        card = _card(apr=0.0, balance_pence=100, min_pct=1.45)
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=100, bills=[]
        )
        assert state.minimum_payment.pence < 2500  # below £25 floor

    def test_opening_balance_stored(self) -> None:
        card = _card(apr=0.0, balance_pence=7500)
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=7500, bills=[]
        )
        assert state.opening_balance.pence == 7500

    def test_minimum_payment_uses_fixed_pence_when_set(self) -> None:
        card = CreditCard(
            id=2,
            name="FixedMin",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=50000),
            interest_rate_apr=None,
            payment_due_day=22,
            minimum_payment_pence=1500,
        )
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=50000, bills=[]
        )
        assert state.minimum_payment.pence == 1500

    def test_card_stored_on_state(self) -> None:
        card = _card(apr=24.9)
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=0, bills=[]
        )
        assert state.card is card

    def test_bills_for_other_card_not_counted(self) -> None:
        card = _card(apr=0.0)
        other_card_id = card.id + 99
        bills = [_bill(name="Other", pence=5000, payment_method_id=other_card_id)]
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=0, bills=bills
        )
        assert state.charges.pence == 0

    def test_payment_targeting_other_card_not_counted(self) -> None:
        card = _card(apr=0.0)
        bills = [
            _bill(
                name="Pmt",
                pence=5000,
                category="credit_payment",
                target_card_id=card.id + 99,
            )
        ]
        state = calculate_card_monthly_state(
            card=card, opening_balance_pence=10000, bills=bills
        )
        assert state.payment_received.pence == 0
