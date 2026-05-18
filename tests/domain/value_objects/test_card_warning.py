"""Tests for CardExhaustionWarning value object."""

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.card_warning import CardExhaustionWarning


class TestCardWarningCreation:
    """Test CardExhaustionWarning creation."""

    def test_create_danger_warning(self) -> None:
        """Test creating danger-level warning."""
        warning = CardExhaustionWarning(
            card_name="CapitalOne",
            available=Amount(pence=50000),
            monthly_charge=Amount(pence=8700),
            monthly_payment=Amount(pence=8000),
            net_monthly=Amount(pence=700),
            months_until_max=3.5,
            status="warning",
        )
        assert warning.is_warning
        assert not warning.is_danger

    def test_create_safe_warning(self) -> None:
        """Test creating safe status."""
        warning = CardExhaustionWarning(
            card_name="Test",
            available=Amount(pence=500000),
            monthly_charge=Amount(pence=1000),
            monthly_payment=Amount(pence=2000),
            net_monthly=Amount(pence=0),
            months_until_max=float("inf"),
            status="ok",
        )
        assert not warning.is_warning
        assert not warning.is_danger

    def test_str_exhausting(self) -> None:
        """Test __str__ for card that's exhausting."""
        warning = CardExhaustionWarning(
            card_name="CapitalOne",
            available=Amount(pence=50000),
            monthly_charge=Amount(pence=8700),
            monthly_payment=Amount(pence=8000),
            net_monthly=Amount(pence=700),
            months_until_max=3.5,
            status="warning",
        )
        str_repr = str(warning)
        assert "CapitalOne" in str_repr
        assert "3.5m" in str_repr

    def test_str_not_exhausting(self) -> None:
        """Test __str__ for card that's not exhausting."""
        warning = CardExhaustionWarning(
            card_name="Test",
            available=Amount(pence=500000),
            monthly_charge=Amount(pence=1000),
            monthly_payment=Amount(pence=2000),
            net_monthly=Amount(pence=0),
            months_until_max=float("inf"),
            status="ok",
        )
        str_repr = str(warning)
        assert "not exhausting" in str_repr
