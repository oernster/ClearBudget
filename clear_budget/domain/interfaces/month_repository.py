"""MonthRepository protocol."""

from typing import Protocol

from clear_budget.domain.value_objects.year_month import YearMonth


class Month(Protocol):
    """A month record with id, year_month, and calculated totals."""

    @property
    def id(self) -> int:
        ...

    @property
    def year_month(self) -> YearMonth:
        ...


class MonthRepository(Protocol):
    """Repository for managing months and their bills/income."""

    def get_or_create(self, *, year_month: YearMonth) -> Month:
        """Get or create a month record."""
        ...

    def get_by_id(self, *, month_id: int) -> Month | None:
        """Get a month by ID."""
        ...

    def list_all(self) -> list[Month]:
        """List all months."""
        ...
