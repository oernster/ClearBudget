"""Tests for SQLitePaymentMethodRepository credit card persistence."""

import pytest

from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)


def _repo(db):
    return SQLitePaymentMethodRepository(db.conn)


def _card(name="TestCard", apr=24.9, min_pct=4.43, balance_pence=100000):
    return CreditCard(
        id=0,
        name=name,
        credit_limit=Amount(pence=200000),
        current_balance_used=Amount(pence=balance_pence),
        interest_rate_apr=apr,
        payment_due_day=8,
        minimum_payment_pence=None,
        minimum_payment_percent=min_pct,
        active=1,
    )


class TestInterestRatePersistence:
    def test_apr_saved_on_add(self, db) -> None:
        repo = _repo(db)
        saved = repo.add_credit_card(card=_card(apr=24.9))
        fetched = repo.get_credit_card_by_id(card_id=saved.id)
        assert fetched.interest_rate_apr == pytest.approx(24.9)

    def test_apr_null_when_zero(self, db) -> None:
        repo = _repo(db)
        card = _card(apr=0.0)
        # Dialog returns None for 0.0; test None persists
        c = CreditCard(
            id=0,
            name="ZeroAPR",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=0),
            interest_rate_apr=None,
            payment_due_day=1,
            active=1,
        )
        saved = repo.add_credit_card(card=c)
        fetched = repo.get_credit_card_by_id(card_id=saved.id)
        assert fetched.interest_rate_apr is None

    def test_apr_updated_by_update_credit_card(self, db) -> None:
        repo = _repo(db)
        saved = repo.add_credit_card(card=_card(apr=24.9))
        updated = CreditCard(
            id=saved.id,
            name=saved.name,
            credit_limit=saved.credit_limit,
            current_balance_used=saved.current_balance_used,
            interest_rate_apr=39.9,
            payment_due_day=saved.payment_due_day,
            minimum_payment_pence=saved.minimum_payment_pence,
            minimum_payment_percent=saved.minimum_payment_percent,
            active=saved.active,
        )
        repo.update_credit_card(card=updated)
        fetched = repo.get_credit_card_by_id(card_id=saved.id)
        assert fetched.interest_rate_apr == pytest.approx(39.9)

    def test_min_pct_saved_on_add(self, db) -> None:
        repo = _repo(db)
        saved = repo.add_credit_card(card=_card(min_pct=4.43))
        fetched = repo.get_credit_card_by_id(card_id=saved.id)
        assert fetched.minimum_payment_percent == pytest.approx(4.43)

    def test_min_pct_updated(self, db) -> None:
        repo = _repo(db)
        saved = repo.add_credit_card(card=_card(min_pct=4.43))
        updated = CreditCard(
            id=saved.id,
            name=saved.name,
            credit_limit=saved.credit_limit,
            current_balance_used=saved.current_balance_used,
            interest_rate_apr=saved.interest_rate_apr,
            payment_due_day=saved.payment_due_day,
            minimum_payment_pence=saved.minimum_payment_pence,
            minimum_payment_percent=1.45,
            active=saved.active,
        )
        repo.update_credit_card(card=updated)
        fetched = repo.get_credit_card_by_id(card_id=saved.id)
        assert fetched.minimum_payment_percent == pytest.approx(1.45)

    def test_expiry_date_saved_on_add(self, db) -> None:
        repo = _repo(db)
        card = CreditCard(
            id=0,
            name="ExpiryCard",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=0),
            interest_rate_apr=24.9,
            payment_due_day=1,
            card_expiry_month=6,
            card_expiry_year=2028,
            active=1,
        )
        saved = repo.add_credit_card(card=card)
        fetched = repo.get_credit_card_by_id(card_id=saved.id)
        assert fetched.card_expiry_month == 6
        assert fetched.card_expiry_year == 2028

    def test_expiry_date_updated(self, db) -> None:
        repo = _repo(db)
        saved = repo.add_credit_card(card=_card())
        updated = CreditCard(
            id=saved.id,
            name=saved.name,
            credit_limit=saved.credit_limit,
            current_balance_used=saved.current_balance_used,
            interest_rate_apr=saved.interest_rate_apr,
            payment_due_day=saved.payment_due_day,
            card_expiry_month=9,
            card_expiry_year=2029,
            minimum_payment_pence=saved.minimum_payment_pence,
            minimum_payment_percent=saved.minimum_payment_percent,
            active=saved.active,
        )
        repo.update_credit_card(card=updated)
        fetched = repo.get_credit_card_by_id(card_id=saved.id)
        assert fetched.card_expiry_month == 9
        assert fetched.card_expiry_year == 2029

    def test_get_all_credit_cards_returns_apr(self, db) -> None:
        repo = _repo(db)
        repo.add_credit_card(card=_card(name="Card1", apr=24.9))
        repo.add_credit_card(card=_card(name="Card2", apr=29.9))
        cards = repo.get_all_credit_cards(include_inactive=True)
        aprs = {c.name: c.interest_rate_apr for c in cards}
        assert aprs["Card1"] == pytest.approx(24.9)
        assert aprs["Card2"] == pytest.approx(29.9)
