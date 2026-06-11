"""CreditCard entity  -  a credit card account."""

from dataclasses import dataclass

from clear_budget.domain.value_objects.amount import Amount


@dataclass(frozen=True, slots=True)
class CreditCard:
    """A credit card payment method.

    Attributes:
        id: Unique identifier
        name: Display name (e.g., "CapitalOne", "Jaja")
        credit_limit: Maximum balance
        current_balance_used: Currently used balance (snapshot)
        interest_rate_apr: Annual percentage rate (optional)
        payment_due_day: Day of month (1-31) when payment is due
        card_expiry_month: Expiry month (1-12, optional)
        card_expiry_year: Expiry year (optional)
        minimum_payment_pence: Minimum payment amount in pence (optional)
        active: 1=active, 0=inactive/closed
        balance_applied_year: Year of the last month folded into
            current_balance_used (optional)
        balance_applied_month: Month of the last month folded into
            current_balance_used (optional)
    """

    id: int
    name: str
    credit_limit: Amount
    current_balance_used: Amount
    interest_rate_apr: float | None = None
    payment_due_day: int = 1
    card_expiry_month: int | None = None
    card_expiry_year: int | None = None
    minimum_payment_pence: int | None = None
    minimum_payment_percent: float | None = None
    active: int = 1
    balance_applied_year: int | None = None
    balance_applied_month: int | None = None

    @property
    def available(self) -> Amount:
        """Available credit remaining."""
        return Amount(pence=self.credit_limit.pence - self.current_balance_used.pence)

    @property
    def utilization_percent(self) -> float:
        """Percentage of credit used (0-100)."""
        if self.credit_limit.pence == 0:
            return 0.0
        return (self.current_balance_used.pence / self.credit_limit.pence) * 100

    def __str__(self) -> str:
        return (
            f"{self.name}: {self.current_balance_used} / {self.credit_limit} "
            f"({self.utilization_percent:.0f}%)"
        )
