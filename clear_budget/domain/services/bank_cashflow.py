"""BankCashflow  -  pure domain service for bank account no-overdraft checking."""

from dataclasses import dataclass

DAYS_PER_YEAR = 365
PENCE_PER_BASIS_POINT_YEAR = 10000  # 1 basis point = 0.01% = 1/10000


@dataclass(frozen=True, slots=True)
class DailyCashflowEvent:
    """A daily income or expense event."""

    day_of_month: int
    amount_pence: int  # negative = expense, positive = income


@dataclass(frozen=True, slots=True)
class MonthCashflowProjection:
    """Day-by-day bank balance projection for one month.

    Attributes:
        opening_balance_pence: Balance at start of month
        closing_balance_pence: Balance at end of month
        min_balance_pence: Lowest balance reached during the month
        min_balance_day: Day of month the lowest balance occurred (None if
            the balance never moves, i.e. no events)
        first_negative_day: First day balance dips below zero (None if never)
        overdraft_exceeded_day: First day balance dips below the overdraft
            limit (None if never breached)
    """

    opening_balance_pence: int
    closing_balance_pence: int
    min_balance_pence: int
    min_balance_day: int | None
    first_negative_day: int | None
    overdraft_exceeded_day: int | None

    def overdraft_severity(self, overdraft_limit_pence: int) -> str:
        """Classify the dip risk for this month.

        Returns:
            "none" - balance never goes negative.
            "amber" - dips negative but stays within the overdraft facility.
            "red" - dips negative with no facility, or exceeds the facility.
        """
        if self.min_balance_pence >= 0:
            return "none"
        if (
            overdraft_limit_pence > 0
            and self.min_balance_pence >= -overdraft_limit_pence
        ):
            return "amber"
        return "red"


class BankCashflowService:
    """Pure service for checking bank account never goes into overdraft.

    Models day-by-day cash flow and identifies first day account goes negative.
    """

    @staticmethod
    def find_first_negative_day(
        *,
        starting_balance_pence: int,
        events: list[DailyCashflowEvent],
    ) -> int | None:
        """Find the first day the account balance goes negative.

        Args:
            starting_balance_pence: Account balance at start of month
            events: List of daily cash flow events, sorted by day

        Returns:
            Day of month (1-31) when balance goes negative, or None if never negative
        """
        balance = starting_balance_pence

        # Sort events by day to process in order
        sorted_events = sorted(events, key=lambda e: e.day_of_month)

        for event in sorted_events:
            balance += event.amount_pence
            if balance < 0:
                return event.day_of_month

        return None

    @staticmethod
    def project_month(
        *,
        starting_balance_pence: int,
        events: list[DailyCashflowEvent],
        overdraft_limit_pence: int = 0,
    ) -> MonthCashflowProjection:
        """Simulate a month's cash flow and report the balance trajectory.

        Args:
            starting_balance_pence: Account balance at start of month
            events: List of daily cash flow events
            overdraft_limit_pence: Size of the overdraft facility (0 if none)

        Returns:
            MonthCashflowProjection describing the month's balance trajectory.
        """
        balance = starting_balance_pence
        min_balance = starting_balance_pence
        min_balance_day: int | None = None
        first_negative_day: int | None = None
        overdraft_exceeded_day: int | None = None

        for event in sorted(events, key=lambda e: e.day_of_month):
            balance += event.amount_pence
            if balance < min_balance:
                min_balance = balance
                min_balance_day = event.day_of_month
            if balance < 0 and first_negative_day is None:
                first_negative_day = event.day_of_month
            if balance < -overdraft_limit_pence and overdraft_exceeded_day is None:
                overdraft_exceeded_day = event.day_of_month

        return MonthCashflowProjection(
            opening_balance_pence=starting_balance_pence,
            closing_balance_pence=balance,
            min_balance_pence=min_balance,
            min_balance_day=min_balance_day,
            first_negative_day=first_negative_day,
            overdraft_exceeded_day=overdraft_exceeded_day,
        )

    @staticmethod
    def estimate_daily_overdraft_interest_pence(
        overdrawn_pence: int, apr_basis_points: int
    ) -> int:
        """Estimate daily interest cost (pence) for an overdrawn amount.

        Args:
            overdrawn_pence: Amount currently overdrawn (positive number)
            apr_basis_points: Overdraft APR in basis points (1bp = 0.01%)

        Returns:
            Estimated interest charge for one day, in pence (0 if not
            overdrawn or no APR set).
        """
        if overdrawn_pence <= 0 or apr_basis_points <= 0:
            return 0
        return round(
            overdrawn_pence
            * apr_basis_points
            / PENCE_PER_BASIS_POINT_YEAR
            / DAYS_PER_YEAR
        )
