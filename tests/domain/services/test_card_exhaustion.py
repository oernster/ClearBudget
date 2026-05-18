"""Tests for CardExhaustionService."""

import math

import pytest

from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.services.card_exhaustion import CardExhaustionService
from clear_budget.domain.value_objects.amount import Amount


class TestCardExhaustionAnalysis:
    """Test credit card exhaustion analysis."""

    def test_analyze_ok_status_five_months(self) -> None:
        """Test card exhaustion status is ok when > 3 months."""
        card = CreditCard(
            id=1,
            name="CapitalOne",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=95000),  # 5000 available
        )
        # At +1000/mo net, exhaustion in 5 months (> 3, so ok)
        warning = CardExhaustionService.analyze(
            card=card,
            monthly_charge=Amount(pence=6000),
            monthly_payment=Amount(pence=5000),
        )
        # 5000 available / 1000 net = 5 months
        assert warning.months_until_max == 5.0
        assert not warning.is_warning
        assert not warning.is_danger

    def test_analyze_danger_imminent(self) -> None:
        """Test danger status when exhaustion <= 1 month."""
        card = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=99000),  # 1000 available
        )
        warning = CardExhaustionService.analyze(
            card=card,
            monthly_charge=Amount(pence=2000),
            monthly_payment=Amount(pence=500),
        )
        # 1000 available / 1500 net = 0.67 months
        assert warning.months_until_max < 1.0
        assert warning.is_danger

    def test_analyze_warning_status(self) -> None:
        """Test warning status when 1 < exhaustion <= 3 months."""
        card = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=95000),  # 5000 available
        )
        warning = CardExhaustionService.analyze(
            card=card,
            monthly_charge=Amount(pence=5000),
            monthly_payment=Amount(pence=2000),
        )
        # 5000 available / 3000 net = 1.67 months (between 1 and 3)
        assert 1 < warning.months_until_max <= 3
        assert warning.is_warning
        assert not warning.is_danger

    def test_analyze_ok_status(self) -> None:
        """Test ok status when exhaustion > 3 months."""
        card = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=50000),  # 50000 available
        )
        warning = CardExhaustionService.analyze(
            card=card,
            monthly_charge=Amount(pence=5000),
            monthly_payment=Amount(pence=1000),
        )
        # 50000 available / 4000 net = 12.5 months
        assert warning.months_until_max > 3
        assert not warning.is_warning
        assert not warning.is_danger

    def test_analyze_zero_net_monthly(self) -> None:
        """Test with zero net monthly (payment equals charge)."""
        card = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=50000),
        )
        warning = CardExhaustionService.analyze(
            card=card,
            monthly_charge=Amount(pence=5000),
            monthly_payment=Amount(pence=5000),
        )
        assert warning.months_until_max == float("inf")
        assert warning.status == "ok"

    def test_analyze_negative_net_monthly(self) -> None:
        """Test with negative net monthly (payment > charge)."""
        card = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=50000),
        )
        warning = CardExhaustionService.analyze(
            card=card,
            monthly_charge=Amount(pence=3000),
            monthly_payment=Amount(pence=5000),
        )
        # When payment > charge, net_monthly is zero (card is being paid down)
        assert warning.months_until_max == float("inf")
        assert warning.net_monthly.pence == 0
        assert warning.status == "ok"

    def test_analyze_fully_utilized_card(self) -> None:
        """Test with fully utilized card (no available credit)."""
        card = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=100000),  # 0 available
        )
        warning = CardExhaustionService.analyze(
            card=card,
            monthly_charge=Amount(pence=5000),
            monthly_payment=Amount(pence=1000),
        )
        assert warning.available.pence == 0
        assert warning.months_until_max == 0.0
        assert warning.is_danger

    def test_analyze_warning_text_danger(self) -> None:
        """Test warning string representation for danger."""
        card = CreditCard(
            id=1,
            name="CapitalOne",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=99000),
        )
        warning = CardExhaustionService.analyze(
            card=card,
            monthly_charge=Amount(pence=2000),
            monthly_payment=Amount(pence=500),
        )
        warning_str = str(warning)
        assert "CapitalOne" in warning_str
        assert "exhausted in" in warning_str

    def test_analyze_warning_text_ok(self) -> None:
        """Test warning string representation for ok status."""
        card = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=10000),
        )
        warning = CardExhaustionService.analyze(
            card=card,
            monthly_charge=Amount(pence=1000),
            monthly_payment=Amount(pence=3000),  # Payment > charge
        )
        warning_str = str(warning)
        assert "not exhausting" in warning_str
