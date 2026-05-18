"""BillRepository protocol."""

from typing import Protocol

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.year_month import YearMonth


class BillRepository(Protocol):
    """Repository for managing bill templates."""

    def list_active_for_month(self, *, year_month: YearMonth) -> list[Bill]:
        """List all active bills for a given month."""
        ...

    def get_by_id(self, *, bill_id: int) -> Bill | None:
        """Get a bill by ID, or None if not found."""
        ...

    def add(self, *, bill: Bill) -> Bill:
        """Add a new bill and return it (with assigned ID if needed)."""
        ...

    def update(self, *, bill: Bill) -> Bill:
        """Update an existing bill."""
        ...

    def deactivate(self, *, bill_id: int) -> None:
        """Deactivate a bill (soft delete)."""
        ...
