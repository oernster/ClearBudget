"""IncomeSource entity — a recurring income stream."""

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
    """

    id: int
    name: str
    amount: Amount
    is_reliable: bool
    day_of_month: int | None
    active: bool = True

    def __str__(self) -> str:
        reliable = "[reliable]" if self.is_reliable else "[variable]"
        return f"{self.name} {self.amount} {reliable}"
