"""Tests for MonthSummary DTO."""

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


class TestMonthSummaryCreation:
    """Test MonthSummary creation."""

    def test_create_with_surplus(self) -> None:
        """Test creating summary with income > bills."""
        summary = MonthSummary(
            year_month=YearMonth(2026, 6),
            total_income=Amount(pence=200000),
            total_bills=Amount(pence=150000),
            balance=Amount(pence=50000),
        )
        assert summary.year_month.year == 2026
        assert summary.year_month.month == 6
        assert summary.balance.pence == 50000

    def test_create_with_deficit(self) -> None:
        """Test creating summary with bills > income."""
        summary = MonthSummary(
            year_month=YearMonth(2026, 7),
            total_income=Amount(pence=100000),
            total_bills=Amount(pence=150000),
            balance=Amount(pence=0),  # Can't store negative
        )
        assert summary.total_bills.pence == 150000
        assert summary.balance.pence == 0

    def test_str(self) -> None:
        """Test string representation."""
        summary = MonthSummary(
            year_month=YearMonth(2026, 6),
            total_income=Amount(pence=200000),
            total_bills=Amount(pence=150000),
            balance=Amount(pence=50000),
        )
        summary_str = str(summary)
        assert "2026-06" in summary_str
        assert "£2000.00" in summary_str
        assert "£1500.00" in summary_str
