"""Tests for BankCashflowService."""

import pytest

from clear_budget.domain.services.bank_cashflow import (
    BankCashflowService,
    DailyCashflowEvent,
    MonthCashflowProjection,
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


class TestProjectMonth:
    """Test BankCashflowService.project_month."""

    def test_never_negative(self) -> None:
        """Balance stays positive throughout."""
        events = [
            DailyCashflowEvent(day_of_month=1, amount_pence=200000),
            DailyCashflowEvent(day_of_month=15, amount_pence=-50000),
        ]
        result = BankCashflowService.project_month(
            starting_balance_pence=100000,
            events=events,
        )
        assert result.opening_balance_pence == 100000
        assert result.closing_balance_pence == 250000
        assert result.min_balance_pence == 100000
        assert result.min_balance_day is None
        assert result.first_negative_day is None
        assert result.overdraft_exceeded_day is None

    def test_dips_negative_then_recovers(self) -> None:
        """Balance dips below zero mid-month but ends positive."""
        events = [
            DailyCashflowEvent(day_of_month=5, amount_pence=-150000),
            DailyCashflowEvent(day_of_month=20, amount_pence=200000),
        ]
        result = BankCashflowService.project_month(
            starting_balance_pence=100000,
            events=events,
        )
        # Day 5: 100000 - 150000 = -50000 (new min)
        # Day 20: -50000 + 200000 = 150000
        assert result.min_balance_pence == -50000
        assert result.min_balance_day == 5
        assert result.first_negative_day == 5
        assert result.closing_balance_pence == 150000
        assert result.overdraft_exceeded_day == 5  # default limit 0

    def test_overdraft_facility_covers_dip(self) -> None:
        """Dip stays within the overdraft facility."""
        events = [
            DailyCashflowEvent(day_of_month=5, amount_pence=-150000),
            DailyCashflowEvent(day_of_month=20, amount_pence=200000),
        ]
        result = BankCashflowService.project_month(
            starting_balance_pence=100000,
            events=events,
            overdraft_limit_pence=100000,  # £1000 facility, dip is -£500
        )
        assert result.min_balance_pence == -50000
        assert result.first_negative_day == 5
        assert result.overdraft_exceeded_day is None

    def test_overdraft_facility_exceeded(self) -> None:
        """Dip goes beyond the overdraft facility."""
        events = [
            DailyCashflowEvent(day_of_month=5, amount_pence=-300000),
        ]
        result = BankCashflowService.project_month(
            starting_balance_pence=100000,
            events=events,
            overdraft_limit_pence=100000,  # £1000 facility, dip is -£2000
        )
        assert result.min_balance_pence == -200000
        assert result.first_negative_day == 5
        assert result.overdraft_exceeded_day == 5

    def test_unsorted_events_processed_in_day_order(self) -> None:
        """Events are sorted by day before simulation."""
        events = [
            DailyCashflowEvent(day_of_month=15, amount_pence=-200000),
            DailyCashflowEvent(day_of_month=1, amount_pence=300000),
        ]
        result = BankCashflowService.project_month(
            starting_balance_pence=100000,
            events=events,
        )
        assert result.closing_balance_pence == 200000
        assert result.first_negative_day is None


class TestOverdraftSeverity:
    """Test MonthCashflowProjection.overdraft_severity."""

    def _projection(self, min_balance_pence: int) -> MonthCashflowProjection:
        return MonthCashflowProjection(
            opening_balance_pence=0,
            closing_balance_pence=0,
            min_balance_pence=min_balance_pence,
            min_balance_day=1,
            first_negative_day=1 if min_balance_pence < 0 else None,
            overdraft_exceeded_day=None,
        )

    def test_none_when_never_negative(self) -> None:
        assert self._projection(0).overdraft_severity(0) == "none"

    def test_red_when_negative_with_no_facility(self) -> None:
        assert self._projection(-100).overdraft_severity(0) == "red"

    def test_amber_when_within_facility(self) -> None:
        assert self._projection(-100).overdraft_severity(50000) == "amber"

    def test_red_when_exceeds_facility(self) -> None:
        assert self._projection(-100000).overdraft_severity(50000) == "red"


class TestEstimateDailyOverdraftInterest:
    """Test BankCashflowService.estimate_daily_overdraft_interest_pence."""

    def test_zero_when_not_overdrawn(self) -> None:
        assert BankCashflowService.estimate_daily_overdraft_interest_pence(0, 3990) == 0

    def test_zero_when_no_apr(self) -> None:
        assert (
            BankCashflowService.estimate_daily_overdraft_interest_pence(100000, 0) == 0
        )

    def test_estimates_daily_interest(self) -> None:
        # £1000 overdrawn at 36.5% APR -> ~£1/day
        result = BankCashflowService.estimate_daily_overdraft_interest_pence(
            100000, 3650
        )
        assert result == 100
