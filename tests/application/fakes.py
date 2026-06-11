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

    def list_active_for_month(
        self, *, year_month: YearMonth, include_inactive: bool = False
    ) -> list[Bill]:
        """List bills active in a given month."""
        return [
            b
            for b in self._bills
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
    _extras: dict[YearMonth, list[IncomeSource]] = field(default_factory=dict)
    _next_extra_id: int = 1000

    def list_active(self) -> list[IncomeSource]:
        """List active income sources."""
        return [s for s in self._sources if s.active]

    def list_active_for_month(
        self, *, year_month: YearMonth, include_inactive: bool = False
    ) -> list[IncomeSource]:
        """List income sources for a given month."""
        if include_inactive:
            return list(self._sources)
        return [s for s in self._sources if s.active and not s.skipped_for_month]

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

    def list_all(self) -> list[IncomeSource]:
        """List all income sources (active and inactive)."""
        return list(self._sources)

    def deactivate(self, *, income_id: int) -> None:
        """Deactivate an income source."""
        for i, s in enumerate(self._sources):
            if s.id == income_id:
                self._sources[i] = replace(s, active=False)

    def hard_delete(self, *, income_id: int) -> None:
        """Permanently remove an income source."""
        self._sources = [s for s in self._sources if s.id != income_id]

    def list_extras_for_month(self, *, year_month: YearMonth) -> list[IncomeSource]:
        """List one-off income entries for a given month."""
        return list(self._extras.get(year_month, []))

    def add_month_extra(
        self, *, year_month: YearMonth, income: IncomeSource
    ) -> IncomeSource:
        """Add a one-off income entry for a given month."""
        added = replace(income, id=self._next_extra_id, is_month_only=True)
        self._next_extra_id += 1
        self._extras.setdefault(year_month, []).append(added)
        return added

    def update_month_extra(
        self, *, year_month: YearMonth, income: IncomeSource
    ) -> IncomeSource:
        """Update a one-off income entry for a given month."""
        for i, extra in enumerate(self._extras.get(year_month, [])):
            if extra.id == income.id:
                self._extras[year_month][i] = income
                return income
        return income

    def delete_month_extra(self, *, extra_id: int) -> None:
        """Permanently remove a one-off income entry."""
        for year_month, extras in self._extras.items():
            self._extras[year_month] = [e for e in extras if e.id != extra_id]


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
                self._cards[i] = replace(
                    c, current_balance_used=Amount(pence=balance_used)
                )

    def set_balance_applied(self, *, card_id: int, year: int, month: int) -> None:
        """Stamp the month whose closing state was folded into the balance."""
        for i, c in enumerate(self._cards):
            if c.id == card_id:
                self._cards[i] = replace(
                    c, balance_applied_year=year, balance_applied_month=month
                )
