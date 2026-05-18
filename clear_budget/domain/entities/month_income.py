"""MonthIncome entity  -  an income entry for a specific month."""

from dataclasses import dataclass

from clear_budget.domain.value_objects.amount import Amount


@dataclass(frozen=True, slots=True)
class MonthIncome:
    """Income entry for a specific month.

    Can be from a recurring source or a one-time/overridden amount.

    Attributes:
        id: Unique identifier
        month_id: Which month (FK to Month)
        income_source_id: Which source this came from (None if ad-hoc)
        name: Income source name
        amount: Actual amount for this month
        is_reliable: Whether to use in forward projections
        day_of_month: Expected arrival day (None if flexible)
    """

    id: int
    month_id: int
    income_source_id: int | None
    name: str
    amount: Amount
    is_reliable: bool
    day_of_month: int | None

    def __str__(self) -> str:
        reliable = "[reliable]" if self.is_reliable else "[variable]"
        return f"{self.name} {self.amount} {reliable}".strip()
