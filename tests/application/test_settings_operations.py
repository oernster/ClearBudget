"""Tests for pure helpers in _settings_operations."""

from clear_budget.application.services._settings_operations import (
    compute_discretionary_buffer_default,
)


class TestComputeDiscretionaryBufferDefault:
    """Test compute_discretionary_buffer_default."""

    def test_uses_twenty_percent_when_above_minimum(self) -> None:
        """20% of balance when that exceeds the £20 floor."""
        assert compute_discretionary_buffer_default(20000) == 4000

    def test_uses_minimum_when_twenty_percent_is_lower(self) -> None:
        """£20 floor applies when 20% of balance is below it."""
        assert compute_discretionary_buffer_default(5000) == 2000

    def test_uses_minimum_for_negative_balance(self) -> None:
        """A negative balance still floors at £20."""
        assert compute_discretionary_buffer_default(-100000) == 2000
