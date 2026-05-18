"""Tests for IncomeSource entity."""

from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount


class TestIncomeSourceCreation:
    """Test IncomeSource creation."""

    def test_create_reliable_income(self) -> None:
        """Test creating reliable income source."""
        inc = IncomeSource(
            id=1,
            name="Universal Credit",
            amount=Amount(pence=120000),
            is_reliable=True,
            day_of_month=21,
        )
        assert inc.name == "Universal Credit"
        assert inc.is_reliable is True

    def test_create_variable_income(self) -> None:
        """Test creating variable income source."""
        inc = IncomeSource(
            id=2,
            name="Freelance",
            amount=Amount(pence=50000),
            is_reliable=False,
            day_of_month=None,
        )
        assert inc.is_reliable is False

    def test_inactive_income(self) -> None:
        """Test creating inactive income."""
        inc = IncomeSource(
            id=3,
            name="Old Job",
            amount=Amount.zero(),
            is_reliable=False,
            day_of_month=None,
            active=False,
        )
        assert inc.active is False

    def test_str_reliable(self) -> None:
        """Test __str__ for reliable income."""
        inc = IncomeSource(
            id=1,
            name="Universal Credit",
            amount=Amount(pence=120000),
            is_reliable=True,
            day_of_month=21,
        )
        assert str(inc) == "Universal Credit £1200.00 [reliable]"

    def test_str_variable(self) -> None:
        """Test __str__ for variable income."""
        inc = IncomeSource(
            id=2,
            name="Freelance",
            amount=Amount(pence=50000),
            is_reliable=False,
            day_of_month=None,
        )
        assert str(inc) == "Freelance £500.00 [variable]"
