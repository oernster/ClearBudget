"""IncomeSource entity  -  a recurring income stream."""

from dataclasses import dataclass

from clear_budget.domain.value_objects.amount import Amount


@dataclass(frozen=True, slots=True)
class IncomeSource:
    """A source of income (e.g., Universal Credit, M+D Loan).

    Attributes:
        id: Unique identifier
        name: Human-readable name
        amount: Monthly amount
        is_reliable: Whether to use this in forward solvency projections
        day_of_month: Expected arrival day (e.g., 1st, 21st)
        active: Whether currently receiving this income
        is_month_only: Whether this is a one-off entry for a single month
        skipped_for_month: Whether this income is skipped for the queried month
        has_month_override: Whether this income has a per-month override
        received_for_month: Whether marked received for the queried month
    """

    id: int
    name: str
    amount: Amount
    is_reliable: bool
    day_of_month: int | None
    active: bool = True
    is_month_only: bool = False
    skipped_for_month: bool = False
    has_month_override: bool = False
    received_for_month: bool = False

    def __str__(self) -> str:
        reliable = "[reliable]" if self.is_reliable else "[variable]"
        return f"{self.name} {self.amount} {reliable}"
