"""Tests for Bill entity."""

import pytest

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


class TestBillCreation:
    """Test Bill creation."""

    def test_create_fixed_bill(self) -> None:
        """Test creating a fixed bill."""
        bill = Bill(
            id=1,
            name="Rent",
            amount=Amount(pence=135000),
            payment_method_id=1,
            category="housing",
            bill_type="fixed",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
        assert bill.name == "Rent"
        assert bill.bill_type == "fixed"

    def test_create_expiring_bill(self) -> None:
        """Test creating an expiring bill."""
        bill = Bill(
            id=2,
            name="Camera Amazon Layaway",
            amount=Amount(pence=6000),
            payment_method_id=1,
            category="one_time",
            bill_type="expiring",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=YearMonth(2026, 11),
        )
        assert bill.bill_type == "expiring"
        assert bill.end_ym == YearMonth(2026, 11)


class TestBillActiveInMonth:
    """Test Bill.is_active_in_month()."""

    def test_active_in_range(self) -> None:
        """Test bill is active within its range."""
        bill = Bill(
            id=1,
            name="Test",
            amount=Amount(pence=1000),
            payment_method_id=1,
            category="test",
            bill_type="fixed",
            day_of_month=None,
            start_ym=YearMonth(2026, 1),
            end_ym=YearMonth(2026, 12),
        )
        assert bill.is_active_in_month(YearMonth(2026, 6))

    def test_inactive_before_start(self) -> None:
        """Test bill is inactive before start_ym."""
        bill = Bill(
            id=1,
            name="Test",
            amount=Amount(pence=1000),
            payment_method_id=1,
            category="test",
            bill_type="fixed",
            day_of_month=None,
            start_ym=YearMonth(2026, 6),
            end_ym=None,
        )
        assert not bill.is_active_in_month(YearMonth(2026, 5))

    def test_inactive_after_end(self) -> None:
        """Test bill is inactive after end_ym."""
        bill = Bill(
            id=1,
            name="Test",
            amount=Amount(pence=1000),
            payment_method_id=1,
            category="test",
            bill_type="expiring",
            day_of_month=None,
            start_ym=YearMonth(2026, 1),
            end_ym=YearMonth(2026, 6),
        )
        assert not bill.is_active_in_month(YearMonth(2026, 7))

    def test_inactive_if_marked_inactive(self) -> None:
        """Test bill is inactive if active=False."""
        bill = Bill(
            id=1,
            name="Test",
            amount=Amount(pence=1000),
            payment_method_id=1,
            category="test",
            bill_type="fixed",
            day_of_month=None,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
            active=False,
        )
        assert not bill.is_active_in_month(YearMonth(2026, 6))

    def test_active_in_start_month(self) -> None:
        """Test bill is active in its start month."""
        bill = Bill(
            id=1,
            name="Test",
            amount=Amount(pence=1000),
            payment_method_id=1,
            category="test",
            bill_type="fixed",
            day_of_month=None,
            start_ym=YearMonth(2026, 6),
            end_ym=None,
        )
        assert bill.is_active_in_month(YearMonth(2026, 6))

    def test_active_in_end_month(self) -> None:
        """Test bill is active in its end month."""
        bill = Bill(
            id=1,
            name="Test",
            amount=Amount(pence=1000),
            payment_method_id=1,
            category="test",
            bill_type="expiring",
            day_of_month=None,
            start_ym=YearMonth(2026, 1),
            end_ym=YearMonth(2026, 6),
        )
        assert bill.is_active_in_month(YearMonth(2026, 6))

    def test_str(self) -> None:
        """Test __str__ formatting."""
        bill = Bill(
            id=1,
            name="Rent",
            amount=Amount(pence=135000),
            payment_method_id=1,
            category="housing",
            bill_type="fixed",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
        assert str(bill) == "Rent (£1350.00)"
