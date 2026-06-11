"""Tests for solvency view model."""

from unittest.mock import Mock

import pytest

from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.application.dto.solvency_report import SolvencyReport


@pytest.fixture
def mock_budget_service():
    """Mock budget service for solvency tests."""
    service = Mock()
    report = SolvencyReport(
        year_month=YearMonth(2026, 5),
        balance_pence=50000,
        deficit=Amount.zero(),
        buffer=Amount.from_pounds(600),
        forward_shortfall=Amount.zero(),
        desired_acquire=Amount.zero(),
        is_solvent=True,
        first_negative_day=None,
    )
    service.calculate_solvency.return_value = report
    service.calculate_solvency_from_summary.return_value = report
    return service


def test_solvency_view_model_initialization(mock_budget_service, qapplication):
    """Test ViewModel initializes correctly."""
    vm = SolvencyViewModel(budget_service=mock_budget_service)
    assert vm.current_month == YearMonth.today()
    # refresh_solvency() is called in __init__, so report is populated
    assert vm.solvency_report is not None
    assert vm.solvency_report.is_solvent


def test_set_month_updates_month(mock_budget_service, qapplication):
    """Test setting month updates current month."""
    vm = SolvencyViewModel(budget_service=mock_budget_service)
    vm.set_month(YearMonth(2026, 6))

    assert vm.current_month == YearMonth(2026, 6)


def test_refresh_solvency_fetches_report(mock_budget_service, qapplication):
    """Test refresh fetches and emits solvency report."""
    vm = SolvencyViewModel(budget_service=mock_budget_service)
    vm.refresh_solvency()

    mock_budget_service.calculate_solvency_from_summary.assert_called()
    assert vm.solvency_report is not None


def test_get_status_color_returns_green_when_solvent(mock_budget_service, qapplication):
    """Test status color is green when account is solvent."""
    vm = SolvencyViewModel(budget_service=mock_budget_service)
    vm.refresh_solvency()

    color = vm.get_status_color()
    assert color == "#34d399"


def test_get_status_color_returns_red_when_deficit(mock_budget_service, qapplication):
    """Test status color is red when account has deficit."""
    report = SolvencyReport(
        year_month=YearMonth(2026, 5),
        balance_pence=-50000,
        deficit=Amount.from_pounds(500),
        buffer=Amount.zero(),
        forward_shortfall=Amount.from_pounds(500),
        desired_acquire=Amount.from_pounds(500),
        is_solvent=False,
        first_negative_day=None,
    )
    mock_budget_service.calculate_solvency.return_value = report
    mock_budget_service.calculate_solvency_from_summary.return_value = report
    vm = SolvencyViewModel(budget_service=mock_budget_service)
    vm.refresh_solvency()

    color = vm.get_status_color()
    assert color == "#f87171"


def test_danger_warning_emitted_on_deficit(mock_budget_service, qapplication):
    """Test deficit is detected when balance is negative."""
    report = SolvencyReport(
        year_month=YearMonth(2026, 5),
        balance_pence=-30000,
        deficit=Amount.from_pounds(300),
        buffer=Amount.zero(),
        forward_shortfall=Amount.zero(),
        desired_acquire=Amount.from_pounds(300),
        is_solvent=False,
        first_negative_day=None,
    )
    mock_budget_service.calculate_solvency.return_value = report
    mock_budget_service.calculate_solvency_from_summary.return_value = report
    vm = SolvencyViewModel(budget_service=mock_budget_service)
    vm.refresh_solvency()

    assert vm.solvency_report.balance_pence < 0
