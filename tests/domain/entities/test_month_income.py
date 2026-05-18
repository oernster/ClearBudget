"""Tests for MonthIncome entity."""

from clear_budget.domain.entities.month_income import MonthIncome
from clear_budget.domain.value_objects.amount import Amount


class TestMonthIncomeCreation:
    """Test MonthIncome creation."""

    def test_create_from_source(self) -> None:
        """Test creating month income from source."""
        mi = MonthIncome(
            id=1,
            month_id=1,
            income_source_id=1,
            name="Universal Credit",
            amount=Amount(pence=120000),
            is_reliable=True,
            day_of_month=21,
        )
        assert mi.income_source_id == 1
        assert mi.is_reliable is True

    def test_create_one_time(self) -> None:
        """Test creating one-time income."""
        mi = MonthIncome(
            id=2,
            month_id=1,
            income_source_id=None,
            name="Tax refund",
            amount=Amount(pence=50000),
            is_reliable=False,
            day_of_month=None,
        )
        assert mi.income_source_id is None
        assert mi.is_reliable is False

    def test_str_reliable(self) -> None:
        """Test __str__ for reliable income."""
        mi = MonthIncome(
            id=1,
            month_id=1,
            income_source_id=1,
            name="Universal Credit",
            amount=Amount(pence=120000),
            is_reliable=True,
            day_of_month=21,
        )
        assert str(mi) == "Universal Credit £1200.00 [reliable]"

    def test_str_variable(self) -> None:
        """Test __str__ for variable income."""
        mi = MonthIncome(
            id=2,
            month_id=1,
            income_source_id=None,
            name="Tax refund",
            amount=Amount(pence=50000),
            is_reliable=False,
            day_of_month=None,
        )
        assert str(mi) == "Tax refund £500.00 [variable]"
