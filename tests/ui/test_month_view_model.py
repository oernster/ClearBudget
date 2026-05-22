"""Tests for month view model."""

from unittest.mock import Mock

import pytest

from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.domain.value_objects.amount import Amount


@pytest.fixture
def mock_budget_service():
    """Mock budget service for testing."""
    service = Mock()
    summary = MonthSummary(
        year_month=YearMonth(2026, 5),
        total_income=Amount.from_pounds(5000),
        total_bills=Amount.from_pounds(3000),
        bank_bills=Amount.from_pounds(3000),
        balance=Amount.from_pounds(2000),
    )
    service.get_month_summary.return_value = summary
    return service


def test_month_view_model_initialization(mock_budget_service, qapplication):
    """Test ViewModel initializes with correct defaults."""
    vm = MonthViewModel(budget_service=mock_budget_service)
    assert vm.current_month == YearMonth(2026, 5)
    # refresh_month_summary() is called in __init__, so summary is populated
    assert vm.month_summary is not None
    assert vm.month_summary.total_income.pence == 500000


def test_set_month_updates_current_month(mock_budget_service, qapplication):
    """Test setting month updates current_month."""
    vm = MonthViewModel(budget_service=mock_budget_service)
    new_month = YearMonth(2026, 6)
    vm.set_month(new_month)

    assert vm.current_month == new_month


def test_set_month_fetches_summary(mock_budget_service, qapplication):
    """Test setting month fetches and emits summary."""
    vm = MonthViewModel(budget_service=mock_budget_service)
    vm.set_month(YearMonth(2026, 6))

    mock_budget_service.get_month_summary.assert_called_with(
        year_month=YearMonth(2026, 6)
    )
    assert vm.month_summary is not None


def test_next_month_advances_calendar(mock_budget_service, qapplication):
    """Test next_month moves forward one month."""
    vm = MonthViewModel(budget_service=mock_budget_service)
    vm.next_month()

    assert vm.current_month == YearMonth(2026, 6)


def test_previous_month_goes_back(mock_budget_service, qapplication):
    """Test previous_month goes back one month."""
    vm = MonthViewModel(budget_service=mock_budget_service)
    vm.set_month(YearMonth(2026, 6))
    vm.previous_month()

    assert vm.current_month == YearMonth(2026, 5)


def test_refresh_month_summary_calls_service(mock_budget_service, qapplication):
    """Test refresh fetches latest summary."""
    vm = MonthViewModel(budget_service=mock_budget_service)
    vm.refresh_month_summary()

    assert mock_budget_service.get_month_summary.called
    assert vm.month_summary is not None
