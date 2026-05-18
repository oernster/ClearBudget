"""Tests for BankCashflowService."""

import pytest

from clear_budget.domain.services.bank_cashflow import (
    BankCashflowService,
    DailyCashflowEvent,
)


class TestBankCashflowAnalysis:
    """Test bank account no-overdraft checking."""

    def test_find_first_negative_immediate(self) -> None:
        """Test finding overdraft on first expense."""
        events = [
            DailyCashflowEvent(day_of_month=1, amount_pence=-150000),  # £1500 out
        ]
        result = BankCashflowService.find_first_negative_day(
            starting_balance_pence=100000,  # £1000
            events=events,
        )
        assert result == 1

    def test_find_first_negative_mid_month(self) -> None:
        """Test finding overdraft mid-month."""
        events = [
            DailyCashflowEvent(day_of_month=1, amount_pence=200000),  # £2000 in
            DailyCashflowEvent(day_of_month=5, amount_pence=-150000),  # £1500 out
            DailyCashflowEvent(day_of_month=15, amount_pence=-200000),  # £2000 out
            DailyCashflowEvent(day_of_month=20, amount_pence=-100000),  # £1000 out
        ]
        result = BankCashflowService.find_first_negative_day(
            starting_balance_pence=100000,  # £1000
            events=events,
        )
        # Day 1: 100000 + 200000 = 300000
        # Day 5: 300000 - 150000 = 150000
        # Day 15: 150000 - 200000 = -50000 (negative!)
        assert result == 15

    def test_find_first_negative_never(self) -> None:
        """Test when account never goes negative."""
        events = [
            DailyCashflowEvent(day_of_month=1, amount_pence=200000),  # £2000 in
            DailyCashflowEvent(day_of_month=5, amount_pence=-100000),  # £1000 out
            DailyCashflowEvent(day_of_month=15, amount_pence=-100000),  # £1000 out
        ]
        result = BankCashflowService.find_first_negative_day(
            starting_balance_pence=100000,  # £1000
            events=events,
        )
        # Day 1: 100000 + 200000 = 300000
        # Day 5: 300000 - 100000 = 200000
        # Day 15: 200000 - 100000 = 100000 (positive)
        assert result is None

    def test_find_first_negative_zero_balance(self) -> None:
        """Test with starting balance exactly zero."""
        events = [
            DailyCashflowEvent(day_of_month=1, amount_pence=-100000),  # £1000 out
        ]
        result = BankCashflowService.find_first_negative_day(
            starting_balance_pence=0,
            events=events,
        )
        assert result == 1

    def test_find_first_negative_exact_zero_after_event(self) -> None:
        """Test when balance becomes exactly zero (not negative)."""
        events = [
            DailyCashflowEvent(day_of_month=1, amount_pence=-100000),  # £1000 out
        ]
        result = BankCashflowService.find_first_negative_day(
            starting_balance_pence=100000,  # £1000
            events=events,
        )
        assert result is None  # Exactly zero is not negative

    def test_find_first_negative_multiple_expenses_same_day(self) -> None:
        """Test with multiple events on same day (they're summed)."""
        events = [
            DailyCashflowEvent(day_of_month=1, amount_pence=100000),  # £1000 in
            DailyCashflowEvent(day_of_month=1, amount_pence=-50000),  # £500 out
            DailyCashflowEvent(day_of_month=1, amount_pence=-75000),  # £750 out
        ]
        result = BankCashflowService.find_first_negative_day(
            starting_balance_pence=0,
            events=events,
        )
        # All on day 1, total: 0 + 100000 - 50000 - 75000 = -25000
        # They're processed in the order given, so:
        # After +100k: 100k
        # After -50k: 50k
        # After -75k: -25k (negative!)
        assert result == 1

    def test_find_first_negative_events_unordered(self) -> None:
        """Test with events provided in non-chronological order."""
        events = [
            DailyCashflowEvent(day_of_month=15, amount_pence=-200000),  # Day 15
            DailyCashflowEvent(day_of_month=1, amount_pence=300000),  # Day 1
            DailyCashflowEvent(day_of_month=5, amount_pence=-150000),  # Day 5
        ]
        result = BankCashflowService.find_first_negative_day(
            starting_balance_pence=100000,
            events=events,
        )
        # Sorted: Day 1, Day 5, Day 15
        # Day 1: 100000 + 300000 = 400000
        # Day 5: 400000 - 150000 = 250000
        # Day 15: 250000 - 200000 = 50000
        assert result is None

    def test_find_first_negative_empty_events(self) -> None:
        """Test with no events."""
        result = BankCashflowService.find_first_negative_day(
            starting_balance_pence=100000,
            events=[],
        )
        assert result is None

    def test_find_first_negative_large_amounts(self) -> None:
        """Test with large amounts."""
        events = [
            DailyCashflowEvent(day_of_month=1, amount_pence=10000000),  # £100k in
            DailyCashflowEvent(day_of_month=15, amount_pence=-15000000),  # £150k out
        ]
        result = BankCashflowService.find_first_negative_day(
            starting_balance_pence=5000000,  # £50k
            events=events,
        )
        # Day 1: 5000000 + 10000000 = 15000000
        # Day 15: 15000000 - 15000000 = 0 (not negative)
        assert result is None

    def test_find_first_negative_income_recovery(self) -> None:
        """Test when income recovers balance after going negative."""
        events = [
            DailyCashflowEvent(day_of_month=5, amount_pence=-200000),  # £2k out
            DailyCashflowEvent(day_of_month=10, amount_pence=300000),  # £3k in
        ]
        result = BankCashflowService.find_first_negative_day(
            starting_balance_pence=100000,  # £1k
            events=events,
        )
        # Day 5: 100000 - 200000 = -100000 (negative!)
        assert result == 5
