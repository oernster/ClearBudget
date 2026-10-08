"""Tests for the live pro-rated credit card balance projection."""

from datetime import date

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.services._card_live_projection import (
    anchored_month_opening_pence,
    bills_inside_entered_balance,
    calculate_live_card_balance,
    month_to_date_net_pence,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


def _card(
    card_id: int = 2,
    balance_pence: int = 10000,
    anchor: tuple[int, int, int] | None = None,
    included: tuple[int, ...] = (),
) -> CreditCard:
    year, month, day = anchor or (None, None, None)
    return CreditCard(
        id=card_id,
        name="TestCard",
        credit_limit=Amount(pence=100000),
        current_balance_used=Amount(pence=balance_pence),
        payment_due_day=22,
        balance_applied_year=year,
        balance_applied_month=month,
        balance_applied_day=day,
        balance_included_bill_ids=included,
    )


def _bill(
    *,
    pence: int,
    payment_method_id: int = 1,
    category: str = "groceries",
    target_card_id: int | None = None,
    day: int | None = None,
    paid: bool = False,
    bill_id: int = 1,
) -> Bill:
    return Bill(
        id=bill_id,
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
        paid_for_month=paid,
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


class TestMonthToDateNetPence:
    def test_charges_only_are_positive(self) -> None:
        card = _card()
        bills = [_bill(pence=1500, payment_method_id=card.id, day=10)]
        net = month_to_date_net_pence(card=card, bills=bills, today=date(2026, 6, 15))
        assert net == 1500

    def test_payment_only_is_negative(self) -> None:
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
        net = month_to_date_net_pence(card=card, bills=bills, today=date(2026, 6, 15))
        assert net == -5000

    def test_charges_minus_payments(self) -> None:
        # Mirrors the reported case: payment so far exceeds charges so far.
        card = _card()
        bills = [
            _bill(pence=6198, payment_method_id=card.id, day=8),
            _bill(
                pence=13000,
                payment_method_id=1,
                category="credit_payment",
                target_card_id=card.id,
                day=11,
            ),
        ]
        net = month_to_date_net_pence(card=card, bills=bills, today=date(2026, 6, 13))
        assert net == 6198 - 13000

    def test_future_dated_bill_excluded(self) -> None:
        card = _card()
        bills = [_bill(pence=1500, payment_method_id=card.id, day=20)]
        net = month_to_date_net_pence(card=card, bills=bills, today=date(2026, 6, 15))
        assert net == 0

    def test_undated_charge_pro_rated(self) -> None:
        card = _card()
        # June has 30 days; day 15 -> half of 3000 = 1500
        bills = [_bill(pence=3000, payment_method_id=card.id, day=None)]
        net = month_to_date_net_pence(card=card, bills=bills, today=date(2026, 6, 15))
        assert net == 1500

    def test_paid_bill_counts_fully_before_its_day(self) -> None:
        # Marked paid means it has happened, whatever day it was due.
        card = _card()
        bills = [_paid_payment(card, day=20)]
        net = month_to_date_net_pence(card=card, bills=bills, today=date(2026, 6, 15))
        assert net == -100000


def _paid_payment(card, *, day: int, pence: int = 100000, bill_id: int = 1) -> Bill:
    """A payment to the card, marked paid, nominally due on `day`."""
    return _bill(
        pence=pence,
        payment_method_id=1,
        category="credit_payment",
        target_card_id=card.id,
        day=day,
        paid=True,
        bill_id=bill_id,
    )


class TestBillsInsideEnteredBalance:
    def test_only_paid_bills_touching_the_card_are_inside(self) -> None:
        card = _card(card_id=2)
        bills = [
            _paid_payment(card, day=14, bill_id=67),
            _bill(pence=700, payment_method_id=2, day=30, paid=True, bill_id=54),
            _bill(pence=900, payment_method_id=2, day=3, bill_id=55),
            _bill(pence=500, payment_method_id=99, day=1, paid=True, bill_id=56),
        ]
        assert bills_inside_entered_balance(card_id=2, bills=bills) == (54, 67)


def _payment_heavy_bills(card) -> list:
    """61.98 of charges (day 8) and a 130.00 payment (day 11) on the card."""
    return [
        _bill(pence=6198, payment_method_id=card.id, day=8),
        _bill(
            pence=13000,
            payment_method_id=1,
            category="credit_payment",
            target_card_id=card.id,
            day=11,
        ),
    ]


class TestAnchoredMonthOpening:
    def test_anchor_month_backs_out_pre_anchor_net(self) -> None:
        # Entered 1592.00 as of day 13; pre-anchor net is 61.98 charges minus
        # 130.00 payment = -68.02, so the start-of-month opening sits above it.
        card = _card(balance_pence=159200, anchor=(2026, 6, 13))
        opening = anchored_month_opening_pence(
            card=card, bills=_payment_heavy_bills(card), year=2026, month=6
        )
        assert opening == 159200 + (13000 - 6198)

    def test_other_month_returns_stored_value_unchanged(self) -> None:
        card = _card(balance_pence=159200, anchor=(2026, 6, 13))
        opening = anchored_month_opening_pence(
            card=card, bills=_payment_heavy_bills(card), year=2026, month=7
        )
        assert opening == 159200

    def test_no_anchor_day_returns_stored_value_unchanged(self) -> None:
        card = _card(balance_pence=159200)
        opening = anchored_month_opening_pence(
            card=card, bills=_payment_heavy_bills(card), year=2026, month=6
        )
        assert opening == 159200

    def test_derived_opening_reproduces_entered_balance_on_anchor_day(self) -> None:
        # The whole point: on the day it was set, the live projection lands back
        # on exactly what the user typed (one number, no hidden transform).
        card = _card(balance_pence=159200, anchor=(2026, 6, 13))
        bills = _payment_heavy_bills(card)
        opening = anchored_month_opening_pence(
            card=card, bills=bills, year=2026, month=6
        )
        live = calculate_live_card_balance(
            card=card,
            opening_balance_pence=opening,
            bills=bills,
            today=date(2026, 6, 13),
        )
        assert live.pence == 159200

    def test_payment_ticked_before_the_balance_was_typed_is_inside_it(
        self,
    ) -> None:
        # The reported case: 3563.85 typed on the 8th after a 1000.00 payment
        # already ticked paid but nominally due on the 14th. The save recorded
        # it as inside the typed figure, so the opening backs it out rather
        # than the month subtracting it a second time.
        card = _card(balance_pence=356385, anchor=(2026, 10, 8), included=(67,))
        bills = [_paid_payment(card, day=14, bill_id=67)]
        opening = anchored_month_opening_pence(
            card=card, bills=bills, year=2026, month=10
        )
        assert opening == 356385 + 100000
        live = calculate_live_card_balance(
            card=card,
            opening_balance_pence=opening,
            bills=bills,
            today=date(2026, 10, 8),
        )
        assert live.pence == 356385

    def test_payment_ticked_after_the_balance_was_typed_still_comes_off(
        self,
    ) -> None:
        # The midnight fold ticks a card payment paid on its own day. Ticked
        # after the balance was typed, it was never inside that figure, so it
        # must still bring the card down.
        card = _card(balance_pence=356385, anchor=(2026, 10, 8))
        bills = [_paid_payment(card, day=21, pence=25000, bill_id=13)]
        opening = anchored_month_opening_pence(
            card=card, bills=bills, year=2026, month=10
        )
        assert opening == 356385
        live = calculate_live_card_balance(
            card=card,
            opening_balance_pence=opening,
            bills=bills,
            today=date(2026, 10, 22),
        )
        assert live.pence == 356385 - 25000
