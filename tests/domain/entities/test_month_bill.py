"""Tests for MonthBill entity."""

from clear_budget.domain.entities.month_bill import MonthBill
from clear_budget.domain.value_objects.amount import Amount


class TestMonthBillCreation:
    """Test MonthBill creation."""

    def test_create_from_template(self) -> None:
        """Test creating month bill from template."""
        mb = MonthBill(
            id=1,
            month_id=1,
            bill_template_id=10,
            name="Rent",
            amount=Amount(pence=135000),
            payment_method_id=1,
            category="housing",
            day_of_month=1,
        )
        assert mb.bill_template_id == 10
        assert mb.is_ad_hoc is False

    def test_create_ad_hoc(self) -> None:
        """Test creating ad-hoc month bill."""
        mb = MonthBill(
            id=2,
            month_id=1,
            bill_template_id=None,
            name="One-time purchase",
            amount=Amount(pence=5000),
            payment_method_id=1,
            category="discretionary",
            day_of_month=None,
            is_ad_hoc=True,
        )
        assert mb.is_ad_hoc is True
        assert mb.bill_template_id is None

    def test_str_from_template(self) -> None:
        """Test __str__ for template-based bill."""
        mb = MonthBill(
            id=1,
            month_id=1,
            bill_template_id=10,
            name="Rent",
            amount=Amount(pence=135000),
            payment_method_id=1,
            category="housing",
            day_of_month=1,
        )
        assert str(mb) == "Rent £1350.00"

    def test_str_ad_hoc(self) -> None:
        """Test __str__ for ad-hoc bill."""
        mb = MonthBill(
            id=2,
            month_id=1,
            bill_template_id=None,
            name="One-time purchase",
            amount=Amount(pence=5000),
            payment_method_id=1,
            category="discretionary",
            day_of_month=None,
            is_ad_hoc=True,
        )
        assert str(mb) == "One-time purchase £50.00 (ad-hoc)"
