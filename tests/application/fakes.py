"""Hand-written fake repositories for testing (no mocking)."""

from dataclasses import dataclass, field, replace

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.interfaces.bill_repository import BillRepository
from clear_budget.domain.interfaces.income_source_repository import (
    IncomeSourceRepository,
)
from clear_budget.domain.interfaces.payment_method_repository import (
    PaymentMethodRepository,
)
from clear_budget.domain.value_objects.year_month import YearMonth


@dataclass
class FakeBillRepository:
    """Fake BillRepository for testing."""

    _bills: list[Bill] = field(default_factory=list)

    def list_active_for_month(self, *, year_month: YearMonth, include_inactive: bool = False) -> list[Bill]:
        """List bills active in a given month."""
        return [
            b for b in self._bills
            if b.is_active_in_month(year_month) and (include_inactive or b.active)
        ]

    def get_by_id(self, *, bill_id: int) -> Bill | None:
        """Get bill by ID."""
        for bill in self._bills:
            if bill.id == bill_id:
                return bill
        return None

    def add(self, *, bill: Bill) -> Bill:
        """Add a bill."""
        self._bills.append(bill)
        return bill

    def update(self, *, bill: Bill) -> Bill:
        """Update a bill."""
        for i, b in enumerate(self._bills):
            if b.id == bill.id:
                self._bills[i] = bill
                return bill
        return bill

    def deactivate(self, *, bill_id: int) -> None:
        """Deactivate a bill."""
        for i, b in enumerate(self._bills):
            if b.id == bill_id:
                self._bills[i] = replace(b, active=False)

    def set_active(self, *, bill_id: int, active: bool) -> None:
        """Set active state of a bill."""
        for i, b in enumerate(self._bills):
            if b.id == bill_id:
                self._bills[i] = replace(b, active=active)

    def hard_delete(self, *, bill_id: int) -> None:
        """Permanently remove a bill."""
        self._bills = [b for b in self._bills if b.id != bill_id]


@dataclass
class FakeIncomeSourceRepository:
    """Fake IncomeSourceRepository for testing."""

    _sources: list[IncomeSource] = field(default_factory=list)

    def list_active(self) -> list[IncomeSource]:
        """List active income sources."""
        return [s for s in self._sources if s.active]

    def list_reliable(self) -> list[IncomeSource]:
        """List reliable income sources."""
        return [s for s in self._sources if s.active and s.is_reliable]

    def get_by_id(self, *, income_id: int) -> IncomeSource | None:
        """Get income source by ID."""
        for source in self._sources:
            if source.id == income_id:
                return source
        return None

    def add(self, *, income: IncomeSource) -> IncomeSource:
        """Add an income source."""
        self._sources.append(income)
        return income

    def update(self, *, income: IncomeSource) -> IncomeSource:
        """Update an income source."""
        for i, s in enumerate(self._sources):
            if s.id == income.id:
                self._sources[i] = income
                return income
        return income

    def deactivate(self, *, income_id: int) -> None:
        """Deactivate an income source."""
        for i, s in enumerate(self._sources):
            if s.id == income_id:
                self._sources[i] = replace(s, active=False)


@dataclass
class FakePaymentMethodRepository:
    """Fake PaymentMethodRepository for testing."""

    _cards: list[CreditCard] = field(default_factory=list)

    def get_all_credit_cards(self, include_inactive: bool = False) -> list[CreditCard]:
        """Get all credit cards."""
        if include_inactive:
            return self._cards
        return [c for c in self._cards if c.active]

    def get_credit_card_by_id(self, *, card_id: int) -> CreditCard | None:
        """Get credit card by ID."""
        for card in self._cards:
            if card.id == card_id:
                return card
        return None

    def add_credit_card(self, *, card: CreditCard) -> CreditCard:
        """Add a credit card."""
        self._cards.append(card)
        return card

    def update_credit_card(self, *, card: CreditCard) -> CreditCard:
        """Update a credit card."""
        for i, c in enumerate(self._cards):
            if c.id == card.id:
                self._cards[i] = card
                return card
        return card

    def deactivate_credit_card(self, *, card_id: int) -> None:
        """Deactivate a credit card."""
        for i, c in enumerate(self._cards):
            if c.id == card_id:
                self._cards[i] = replace(c, active=0)

    def update_credit_card_balance(self, *, card_id: int, balance_used: int) -> None:
        """Update credit card balance."""
        from clear_budget.domain.value_objects.amount import Amount
        for i, c in enumerate(self._cards):
            if c.id == card_id:
                self._cards[i] = replace(c, current_balance_used=Amount(pence=balance_used))
