"""CardExhaustion  -  pure domain service for credit card exhaustion calculations."""

from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.card_warning import CardExhaustionWarning


class CardExhaustionService:
    """Pure service for calculating when a credit card will max out."""

    @staticmethod
    def analyze(
        *,
        card: CreditCard,
        monthly_charge: Amount,
        monthly_payment: Amount,
    ) -> CardExhaustionWarning:
        """Analyze credit card exhaustion risk.

        Args:
            card: The credit card to analyze
            monthly_charge: Charges added to the card per month
            monthly_payment: Payments made from bank to pay down the card

        Returns:
            CardExhaustionWarning with status and months_until_max
        """
        available = card.available

        # Calculate net monthly as a pence integer (can be negative)
        net_monthly_pence = monthly_charge.pence - monthly_payment.pence

        # Create net_monthly Amount for non-negative value representation
        # Use absolute if negative (for display purposes)
        if net_monthly_pence <= 0:
            net_monthly = Amount.zero()
            months_until_max = float("inf")
        else:
            net_monthly = Amount(pence=net_monthly_pence)
            # Calculate how many months until available credit runs out
            months_until_max = available.pence / net_monthly_pence

        # Determine status based on months_until_max
        if months_until_max <= 1:
            status = "danger"
        elif months_until_max <= 3:
            status = "warning"
        else:
            status = "ok"

        return CardExhaustionWarning(
            card_name=card.name,
            available=available,
            monthly_charge=monthly_charge,
            monthly_payment=monthly_payment,
            net_monthly=net_monthly,
            months_until_max=months_until_max,
            status=status,
        )
