"""CommitmentRepository protocol."""

from typing import Protocol

from clear_budget.domain.entities.commitment import Commitment
from clear_budget.domain.value_objects.year_month import YearMonth


class CommitmentRepository(Protocol):
    """Repository for the obligations a budget is reserving for."""

    def list_all(self, *, include_inactive: bool = False) -> list[Commitment]:
        """Every commitment, newest due date last."""
        ...

    def list_for_month(self, *, year_month: YearMonth) -> list[Commitment]:
        """Those being reserved for during `year_month`."""
        ...

    def get_by_id(self, *, commitment_id: int) -> Commitment | None:
        """One commitment by id; None when there is none."""
        ...

    def add(self, *, commitment: Commitment) -> Commitment:
        """Store a new commitment and return it carrying its assigned id."""
        ...

    def update(self, *, commitment: Commitment) -> Commitment:
        """Store changes to an existing commitment."""
        ...

    def end_from(self, *, commitment_id: int, final_month: YearMonth) -> None:
        """Stop reserving after `final_month`, keeping the months it ran in."""
        ...

    def delete(self, *, commitment_id: int) -> None:
        """Remove a commitment outright, including the months it ran in."""
        ...
