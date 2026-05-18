"""PaymentMethodRepository protocol."""

from typing import Protocol

from clear_budget.domain.entities.credit_card import CreditCard


class PaymentMethodRepository(Protocol):
    """Repository for managing payment methods (credit cards, bank account)."""

    def get_all_credit_cards(self) -> list[CreditCard]:
        """Get all credit cards."""
        ...

    def get_credit_card_by_id(self, *, card_id: int) -> CreditCard | None:
        """Get a credit card by ID."""
        ...

    def update_credit_card_balance(self, *, card_id: int, balance_used: int) -> None:
        """Update a credit card's used balance (in pence)."""
        ...
