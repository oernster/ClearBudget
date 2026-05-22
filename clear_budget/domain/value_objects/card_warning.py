"""CardExhaustionWarning value object  -  when a credit card will max out."""

from dataclasses import dataclass

from clear_budget.domain.value_objects.amount import Amount


@dataclass(frozen=True, slots=True)
class CardExhaustionWarning:
    """Warning that a credit card will exhaust within a certain timeframe.

    Attributes:
        card_name: Name of the credit card
        available: Currently available credit
        monthly_charge: Monthly bills charged to this card
        monthly_payment: Monthly payment FROM bank TO this card
        net_monthly: monthly_charge - monthly_payment (can be positive or negative)
        months_until_max: Estimated months until exhaustion (inf if net_monthly <= 0)
        status: 'danger' if <= 1 month, 'warning' if <= 3 months
    """

    card_name: str
    available: Amount
    monthly_charge: Amount
    monthly_payment: Amount
    net_monthly: Amount
    months_until_max: float
    status: str  # 'danger', 'warning', 'ok'

    @property
    def is_danger(self) -> bool:
        """True if exhaustion is imminent (<=1 month)."""
        return self.status == "danger"

    @property
    def is_warning(self) -> bool:
        """True if exhaustion is within 3 months."""
        return self.status == "warning"

    def __str__(self) -> str:
        if self.months_until_max == float("inf"):
            return (
                f"{self.card_name}: {self.available} available, "
                f"-{self.net_monthly}/mo (not exhausting)"
            )
        return (
            f"{self.card_name}: {self.available} available, "
            f"+{self.net_monthly}/mo (exhausted in {self.months_until_max:.1f}m)"
        )
