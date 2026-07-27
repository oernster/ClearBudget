"""ProjectionMonth DTO - one month's place on the path of solvency."""

from dataclasses import dataclass

# The three states a month can be in. They match the traffic light the
# Solvency page already uses; the names are repeated here rather than
# imported because the UI layer owns the colours and the application layer
# may not depend on it.
STATE_SAFE = "safe"
STATE_CAUTION = "caution"
STATE_RED = "red"


@dataclass(frozen=True, slots=True)
class ProjectionMonth:
    """How one month is projected to go, for a multi-month report.

    Attributes:
        year: Calendar year.
        month: Calendar month, 1 to 12.
        label: Display name, e.g. "March 2026".
        opening_pence: Projected bank balance the month opens with, before any
            of its own bills or income. Equals the previous month's close, so
            the range reads as one chain, and equals closing_pence less
            net_pence.
        closing_pence: Projected bank balance at the end of the month's last day.
        low_pence: The lowest day-end bank balance reached in the month.
        low_day: Day of the month the low falls on, 1-based.
        income_pence: Total reliable income for the month.
        bank_bills_pence: Total bills paid from the bank account.
        floor_pence: The agreed overdraft floor, zero or negative. Below it a
            payment does not clear; above it but below zero is arranged
            borrowing.
    """

    year: int
    month: int
    label: str
    opening_pence: int
    closing_pence: int
    low_pence: int
    low_day: int
    income_pence: int
    bank_bills_pence: int
    floor_pence: int

    @property
    def net_pence(self) -> int:
        """What the month adds to or takes off the balance."""
        return self.income_pence - self.bank_bills_pence

    @property
    def state(self) -> str:
        """The month's traffic light, on the same rule as the Solvency page.

        Red is the balance going below the agreed floor, which is real
        trouble. Caution is dipping below zero into an arranged facility, or
        ending the month lower than it started, which is survivable but not
        sustainable. Anything else is safe.
        """
        if self.low_pence < self.floor_pence:
            return STATE_RED
        if self.low_pence < 0 or self.closing_pence < self.opening_pence:
            return STATE_CAUTION
        return STATE_SAFE
