"""IncomeSourceRepository protocol."""

from typing import Protocol

from clear_budget.domain.entities.income_source import IncomeSource


class IncomeSourceRepository(Protocol):
    """Repository for managing income sources."""

    def list_active(self) -> list[IncomeSource]:
        """List all active income sources."""
        ...

    def list_all(self) -> list[IncomeSource]:
        """List all income sources including inactive."""
        ...

    def list_reliable(self) -> list[IncomeSource]:
        """List all reliable (forward-projectable) income sources."""
        ...

    def get_by_id(self, *, income_id: int) -> IncomeSource | None:
        """Get an income source by ID."""
        ...

    def add(self, *, income: IncomeSource) -> IncomeSource:
        """Add a new income source."""
        ...

    def update(self, *, income: IncomeSource) -> IncomeSource:
        """Update an income source."""
        ...

    def deactivate(self, *, income_id: int) -> None:
        """Deactivate an income source."""
        ...

    def hard_delete(self, *, income_id: int) -> None:
        """Permanently remove an income source from the database."""
        ...
