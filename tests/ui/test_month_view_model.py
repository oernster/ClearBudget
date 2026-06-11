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
    assert vm.current_month == YearMonth.today()
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

    assert vm.current_month == YearMonth.today().next_month()


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


def test_add_income_month_extra_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """add_income_month_extra delegates to service for current month and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)
    income = Mock()

    vm.add_income_month_extra(income=income)

    mock_budget_service.add_income_month_extra.assert_called_with(
        income=income, year_month=vm.current_month
    )
    assert mock_budget_service.get_month_summary.called


def test_update_income_month_extra_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """update_income_month_extra delegates to service for current month and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)
    income = Mock()

    vm.update_income_month_extra(income=income)

    mock_budget_service.update_income_month_extra.assert_called_with(
        income=income, year_month=vm.current_month
    )
    assert mock_budget_service.get_month_summary.called


def test_delete_income_month_extra_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """delete_income_month_extra delegates to service and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)

    vm.delete_income_month_extra(extra_id=42)

    mock_budget_service.delete_income_month_extra.assert_called_with(extra_id=42)
    assert mock_budget_service.get_month_summary.called


def test_mark_bill_paid_for_month_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """mark_bill_paid_for_month delegates to service for current month and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)

    vm.mark_bill_paid_for_month(bill_id=7)

    mock_budget_service.mark_bill_paid_for_month.assert_called_with(
        bill_id=7, year_month=vm.current_month
    )
    assert mock_budget_service.get_month_summary.called


def test_unmark_bill_paid_for_month_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """unmark_bill_paid_for_month delegates to service for current month and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)

    vm.unmark_bill_paid_for_month(bill_id=7)

    mock_budget_service.unmark_bill_paid_for_month.assert_called_with(
        bill_id=7, year_month=vm.current_month
    )
    assert mock_budget_service.get_month_summary.called


def test_update_income_for_month_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """update_income_for_month delegates to service for current month and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)
    income = Mock()

    vm.update_income_for_month(income=income)

    mock_budget_service.update_income_for_month.assert_called_with(
        income=income, year_month=vm.current_month
    )
    assert mock_budget_service.get_month_summary.called


def test_delete_income_month_override_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """delete_income_month_override delegates to service and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)

    vm.delete_income_month_override(income_id=3)

    mock_budget_service.delete_income_month_override.assert_called_with(
        income_id=3, year_month=vm.current_month
    )
    assert mock_budget_service.get_month_summary.called


def test_skip_income_for_month_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """skip_income_for_month delegates to service and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)

    vm.skip_income_for_month(income_id=3)

    mock_budget_service.skip_income_for_month.assert_called_with(
        income_id=3, year_month=vm.current_month
    )
    assert mock_budget_service.get_month_summary.called


def test_unskip_income_for_month_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """unskip_income_for_month delegates to service and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)

    vm.unskip_income_for_month(income_id=3)

    mock_budget_service.unskip_income_for_month.assert_called_with(
        income_id=3, year_month=vm.current_month
    )
    assert mock_budget_service.get_month_summary.called


def test_mark_income_received_for_month_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """mark_income_received_for_month delegates to service and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)

    vm.mark_income_received_for_month(income_id=3)

    mock_budget_service.mark_income_received_for_month.assert_called_with(
        income_id=3, year_month=vm.current_month
    )
    assert mock_budget_service.get_month_summary.called


def test_unmark_income_received_for_month_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """unmark_income_received_for_month delegates to service and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)

    vm.unmark_income_received_for_month(income_id=3)

    mock_budget_service.unmark_income_received_for_month.assert_called_with(
        income_id=3, year_month=vm.current_month
    )
    assert mock_budget_service.get_month_summary.called


def test_mark_income_extra_received_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """mark_income_extra_received delegates to service and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)

    vm.mark_income_extra_received(extra_id=42)

    mock_budget_service.mark_income_extra_received.assert_called_with(extra_id=42)
    assert mock_budget_service.get_month_summary.called


def test_unmark_income_extra_received_calls_service_and_refreshes(
    mock_budget_service, qapplication
):
    """unmark_income_extra_received delegates to service and refreshes."""
    vm = MonthViewModel(budget_service=mock_budget_service)

    vm.unmark_income_extra_received(extra_id=42)

    mock_budget_service.unmark_income_extra_received.assert_called_with(extra_id=42)
    assert mock_budget_service.get_month_summary.called
