"""PaymentMethodRepository protocol."""

from typing import Protocol

from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.credit_limit_change import CreditLimitChange


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

    def update_credit_card_limit(self, *, card_id: int, limit_pence: int) -> None:
        """Update a credit card's current credit limit (in pence)."""
        ...

    def set_credit_limit_changes(
        self, *, card_id: int, changes: tuple[CreditLimitChange, ...]
    ) -> None:
        """Replace all scheduled limit changes for a card."""
        ...
