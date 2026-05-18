"""Tests for SolvencyReport DTO."""

from clear_budget.application.dto.solvency_report import SolvencyReport
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


class TestSolvencyReportCreation:
    """Test SolvencyReport creation."""

    def test_create_solvent_report(self) -> None:
        """Test creating report for solvent month."""
        report = SolvencyReport(
            year_month=YearMonth(2026, 6),
            balance_pence=100000,
            deficit=Amount.zero(),
            buffer=Amount(pence=60000),
            forward_shortfall=Amount.zero(),
            desired_acquire=Amount(pence=60000),
            is_solvent=True,
            first_negative_day=None,
        )
        assert report.is_solvent
        assert report.first_negative_day is None
        assert report.balance_pence == 100000

    def test_create_insolvent_report(self) -> None:
        """Test creating report for insolvent month."""
        report = SolvencyReport(
            year_month=YearMonth(2026, 7),
            balance_pence=-50000,
            deficit=Amount(pence=50000),
            buffer=Amount(pence=60000),
            forward_shortfall=Amount(pence=30000),
            desired_acquire=Amount(pence=140000),
            is_solvent=False,
            first_negative_day=15,
        )
        assert not report.is_solvent
        assert report.first_negative_day == 15
        assert report.balance_pence == -50000

    def test_str_solvent(self) -> None:
        """Test string representation for solvent."""
        report = SolvencyReport(
            year_month=YearMonth(2026, 6),
            balance_pence=100000,
            deficit=Amount.zero(),
            buffer=Amount(pence=60000),
            forward_shortfall=Amount.zero(),
            desired_acquire=Amount(pence=60000),
            is_solvent=True,
            first_negative_day=None,
        )
        report_str = str(report)
        assert "SOLVENT" in report_str
        assert "2026-06" in report_str

    def test_str_insolvent(self) -> None:
        """Test string representation for insolvent."""
        report = SolvencyReport(
            year_month=YearMonth(2026, 7),
            balance_pence=-50000,
            deficit=Amount(pence=50000),
            buffer=Amount(pence=60000),
            forward_shortfall=Amount(pence=30000),
            desired_acquire=Amount(pence=140000),
            is_solvent=False,
            first_negative_day=15,
        )
        report_str = str(report)
        assert "DEFICIT" in report_str
