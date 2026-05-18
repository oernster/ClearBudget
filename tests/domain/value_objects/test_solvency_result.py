"""Tests for SolvencyResult value object."""

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.solvency_result import SolvencyResult


class TestSolvencyResultCreation:
    """Test SolvencyResult creation."""

    def test_create_with_surplus(self) -> None:
        """Test creating with positive balance."""
        result = SolvencyResult(
            balance=50000,
            deficit=Amount.zero(),
            buffer=Amount(pence=60000),
            forward_shortfall=Amount.zero(),
            desired_acquire=Amount.zero(),
        )
        assert result.is_solvent
        assert not result.has_deficit

    def test_create_with_deficit(self) -> None:
        """Test creating with negative balance."""
        result = SolvencyResult(
            balance=-10000,  # negative pence
            deficit=Amount(pence=10000),
            buffer=Amount(pence=60000),
            forward_shortfall=Amount(pence=20000),
            desired_acquire=Amount(pence=90000),
        )
        assert result.has_deficit
        assert not result.is_solvent

    def test_str_surplus(self) -> None:
        """Test __str__ for surplus."""
        result = SolvencyResult(
            balance=50000,
            deficit=Amount.zero(),
            buffer=Amount(pence=60000),
            forward_shortfall=Amount.zero(),
            desired_acquire=Amount.zero(),
        )
        str_repr = str(result)
        assert "50000" in str_repr
        assert "surplus" in str_repr

    def test_str_deficit(self) -> None:
        """Test __str__ for deficit."""
        result = SolvencyResult(
            balance=-10000,
            deficit=Amount(pence=10000),
            buffer=Amount(pence=60000),
            forward_shortfall=Amount(pence=20000),
            desired_acquire=Amount(pence=90000),
        )
        str_repr = str(result)
        assert "-10000" in str_repr
        assert "deficit" in str_repr
