"""SolvencyResult value object  -  outcome of solvency calculations."""

from dataclasses import dataclass

from clear_budget.domain.value_objects.amount import Amount


@dataclass(frozen=True, slots=True)
class SolvencyResult:
    """Result of solvency analysis for a given month.

    Attributes:
        balance: Total income - total bills in pence (can be negative)
        deficit: Absolute value of negative balance (0 if surplus)
        buffer: Safety cushion amount (typically £600)
        forward_shortfall: Sum of shortfalls in next 2 months (reliable income only)
        desired_acquire: deficit + buffer + forward_shortfall (total to acquire)
    """

    balance: int  # pence, can be negative
    deficit: Amount
    buffer: Amount
    forward_shortfall: Amount
    desired_acquire: Amount

    @property
    def has_deficit(self) -> bool:
        """True if balance is negative."""
        return self.balance < 0

    @property
    def is_solvent(self) -> bool:
        """True if balance is non-negative."""
        return not self.has_deficit

    def __str__(self) -> str:
        if self.has_deficit:
            return (
                f"Solvency(balance={self.balance}, "
                f"deficit={self.deficit}, "
                f"desired_acquire={self.desired_acquire})"
            )
        return f"Solvency(balance={self.balance}, surplus)"
