"""SolvencyReport DTO — complete solvency analysis for a month."""

from dataclasses import dataclass

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


@dataclass(frozen=True, slots=True)
class SolvencyReport:
    """Complete solvency analysis crossing the application boundary.

    Attributes:
        year_month: The month analyzed
        balance_pence: Income - bills for this month (can be negative, in pence)
        deficit: Absolute shortfall if balance < 0
        buffer: Safety cushion (typically £600)
        forward_shortfall: Projected shortfall in next 2 months
        desired_acquire: deficit + buffer + forward_shortfall (acquire target)
        is_solvent: True if balance >= 0
        first_negative_day: Day account goes into overdraft (None if never)
    """

    year_month: YearMonth
    balance_pence: int  # Can be negative
    deficit: Amount
    buffer: Amount
    forward_shortfall: Amount
    desired_acquire: Amount
    is_solvent: bool
    first_negative_day: int | None

    def __str__(self) -> str:
        status = "SOLVENT" if self.is_solvent else "DEFICIT"
        return (
            f"{self.year_month} {status}: "
            f"balance_pence={self.balance_pence} "
            f"desired_acquire={self.desired_acquire}"
        )
