"""Tests for CreditCard entity."""

from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount


class TestCreditCardCreation:
    """Test CreditCard creation."""

    def test_create_credit_card(self) -> None:
        """Test creating a credit card."""
        cc = CreditCard(
            id=1,
            name="CapitalOne",
            credit_limit=Amount(pence=175000),
            current_balance_used=Amount(pence=141536),
        )
        assert cc.name == "CapitalOne"
        assert cc.credit_limit.pounds == 1750.0


class TestCreditCardAvailable:
    """Test CreditCard.available property."""

    def test_available_credit(self) -> None:
        """Test calculating available credit."""
        cc = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=75000),
        )
        assert cc.available.pence == 25000

    def test_fully_utilized(self) -> None:
        """Test when card is fully utilized."""
        cc = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=100000),
        )
        assert cc.available.pence == 0


class TestCreditCardUtilization:
    """Test CreditCard.utilization_percent property."""

    def test_utilization_zero_balance(self) -> None:
        """Test 0% utilization with zero balance."""
        cc = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount.zero(),
        )
        assert cc.utilization_percent == 0.0

    def test_utilization_zero_limit(self) -> None:
        """Test utilization with zero credit limit."""
        cc = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount.zero(),
            current_balance_used=Amount.zero(),
        )
        assert cc.utilization_percent == 0.0

    def test_utilization_fifty(self) -> None:
        """Test 50% utilization."""
        cc = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=50000),
        )
        assert cc.utilization_percent == 50.0

    def test_utilization_full(self) -> None:
        """Test 100% utilization."""
        cc = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=100000),
        )
        assert cc.utilization_percent == 100.0


class TestCreditCardFormatting:
    """Test CreditCard string formatting."""

    def test_str(self) -> None:
        """Test __str__ formatting."""
        cc = CreditCard(
            id=1,
            name="CapitalOne",
            credit_limit=Amount(pence=175000),
            current_balance_used=Amount(pence=141536),
        )
        assert "CapitalOne" in str(cc)
        assert "£1415.36" in str(cc)
        assert "£1750.00" in str(cc)

    def test_str_full_utilization(self) -> None:
        """Test __str__ with 100% utilization."""
        cc = CreditCard(
            id=1,
            name="Test",
            credit_limit=Amount(pence=100000),
            current_balance_used=Amount(pence=100000),
        )
        str_repr = str(cc)
        assert "100%" in str_repr
