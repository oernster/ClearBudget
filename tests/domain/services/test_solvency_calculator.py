"""Tests for SolvencyCalculatorService."""

import pytest

from clear_budget.domain.entities.month_bill import MonthBill
from clear_budget.domain.entities.month_income import MonthIncome
from clear_budget.domain.services.solvency_calculator import SolvencyCalculatorService
from clear_budget.domain.value_objects.amount import Amount


class TestSolvencyCalculatorBasic:
    """Test basic solvency calculations."""

    def test_calculate_surplus(self) -> None:
        """Test calculating solvency with surplus."""
        bills = [
            MonthBill(
                id=1,
                month_id=1,
                bill_template_id=1,
                name="Rent",
                amount=Amount(pence=135000),
                payment_method_id=1,
                category="housing",
                day_of_month=1,
            ),
        ]
        income = [
            MonthIncome(
                id=1,
                month_id=1,
                income_source_id=1,
                name="UC",
                amount=Amount(pence=200000),
                is_reliable=True,
                day_of_month=1,
            ),
        ]
        result = SolvencyCalculatorService.calculate(
            month_bills=bills,
            month_income=income,
            next_two_months_bills=[[], []],
            next_two_months_income=[[], []],
        )
        assert result.balance == 65000
        assert result.is_solvent
        assert not result.has_deficit
        assert result.deficit == Amount.zero()

    def test_calculate_deficit(self) -> None:
        """Test calculating solvency with deficit."""
        bills = [
            MonthBill(
                id=1,
                month_id=1,
                bill_template_id=1,
                name="Rent",
                amount=Amount(pence=200000),
                payment_method_id=1,
                category="housing",
                day_of_month=1,
            ),
        ]
        income = [
            MonthIncome(
                id=1,
                month_id=1,
                income_source_id=1,
                name="UC",
                amount=Amount(pence=150000),
                is_reliable=True,
                day_of_month=1,
            ),
        ]
        result = SolvencyCalculatorService.calculate(
            month_bills=bills,
            month_income=income,
            next_two_months_bills=[[], []],
            next_two_months_income=[[], []],
        )
        assert result.balance == -50000
        assert not result.is_solvent
        assert result.has_deficit
        assert result.deficit.pence == 50000

    def test_calculate_with_forward_shortfall(self) -> None:
        """Test solvency with forward looking shortfall."""
        current_bills = [
            MonthBill(
                id=1,
                month_id=1,
                bill_template_id=1,
                name="Rent",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                day_of_month=1,
            ),
        ]
        current_income = [
            MonthIncome(
                id=1,
                month_id=1,
                income_source_id=1,
                name="UC",
                amount=Amount(pence=150000),
                is_reliable=True,
                day_of_month=1,
            ),
        ]
        # Next month will have 200k bills but only 100k income (100k shortfall)
        next_month_bills = [
            MonthBill(
                id=2,
                month_id=2,
                bill_template_id=1,
                name="Car payment",
                amount=Amount(pence=200000),
                payment_method_id=1,
                category="discretionary",
                day_of_month=15,
            ),
        ]
        next_month_income = [
            MonthIncome(
                id=2,
                month_id=2,
                income_source_id=1,
                name="UC",
                amount=Amount(pence=100000),
                is_reliable=True,
                day_of_month=1,
            ),
        ]
        result = SolvencyCalculatorService.calculate(
            month_bills=current_bills,
            month_income=current_income,
            next_two_months_bills=[next_month_bills, []],
            next_two_months_income=[next_month_income, []],
        )
        assert result.balance == 50000  # Current month surplus
        assert result.forward_shortfall.pence == 100000
        assert result.desired_acquire.pence == 100000 + 60000  # shortfall + buffer

    def test_calculate_zero_amounts(self) -> None:
        """Test with empty bills/income lists."""
        result = SolvencyCalculatorService.calculate(
            month_bills=[],
            month_income=[],
            next_two_months_bills=[[], []],
            next_two_months_income=[[], []],
        )
        assert result.balance == 0
        assert not result.has_deficit
        assert result.forward_shortfall == Amount.zero()

    def test_calculate_with_multiple_bills(self) -> None:
        """Test summing multiple bills."""
        bills = [
            MonthBill(
                id=1,
                month_id=1,
                bill_template_id=1,
                name="Rent",
                amount=Amount(pence=100000),
                payment_method_id=1,
                category="housing",
                day_of_month=1,
            ),
            MonthBill(
                id=2,
                month_id=1,
                bill_template_id=2,
                name="Utilities",
                amount=Amount(pence=5000),
                payment_method_id=1,
                category="utilities",
                day_of_month=15,
            ),
        ]
        income = [
            MonthIncome(
                id=1,
                month_id=1,
                income_source_id=1,
                name="UC",
                amount=Amount(pence=150000),
                is_reliable=True,
                day_of_month=1,
            ),
        ]
        result = SolvencyCalculatorService.calculate(
            month_bills=bills,
            month_income=income,
            next_two_months_bills=[[], []],
            next_two_months_income=[[], []],
        )
        assert result.balance == 45000
        assert not result.has_deficit

    def test_calculate_custom_buffer(self) -> None:
        """Test with custom buffer amount."""
        result = SolvencyCalculatorService.calculate(
            month_bills=[],
            month_income=[],
            next_two_months_bills=[[], []],
            next_two_months_income=[[], []],
            buffer=Amount.from_pounds(1000),
        )
        assert result.buffer.pounds == 1000.0
        assert result.desired_acquire.pence == 100000  # 1000 pounds in pence
