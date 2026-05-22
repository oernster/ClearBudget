"""BankCashflow  -  pure domain service for bank account no-overdraft checking."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DailyCashflowEvent:
    """A daily income or expense event."""

    day_of_month: int
    amount_pence: int  # negative = expense, positive = income


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
