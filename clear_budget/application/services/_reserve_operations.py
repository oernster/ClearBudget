"""Reserves adapter for BudgetService, extracted for the LOC limit.

Bridges the stored commitments to the pure floor. Everything the view needs
to draw a row comes from here, so the page never reaches past the service to
a repository of its own and never does the accrual arithmetic itself.

The emergency buffer is the SAME stored setting the Recommendations page has
always used. It moved to this page rather than being duplicated: a buffer and
a reserve are the same kind of object, money held back, so there is one of
them and one place it is set.
"""

from dataclasses import dataclass
from datetime import date

from clear_budget.domain.entities.commitment import Commitment
from clear_budget.domain.services.reserve_accrual import (
    accrued_pence,
    monthly_rate_pence,
    natural_rate_pence,
    reserve_pence,
)
from clear_budget.domain.services._prorating import days_in_month
from clear_budget.domain.services.reserve_floor import ReserveFloor
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


@dataclass(frozen=True, slots=True)
class ReserveRow:
    """One commitment as the page shows it.

    Attributes:
        commitment: The stored obligation itself
        monthly_pence: What has to be found each month from today
        natural_pence: What it settles at once a full cycle is available
        held_pence: What has accrued for the current cycle so far
        outstanding_pence: What still has to be found for this occurrence
        is_steep: Whether the first cycle is short, so the monthly figure is
            harsher than the rate it settles at
    """

    commitment: Commitment
    monthly_pence: int
    natural_pence: int
    held_pence: int
    outstanding_pence: int
    is_steep: bool


class ReserveOperationsMixin:
    """Commitment reads and writes, plus the floor they build."""

    def list_commitments(self, *, include_inactive: bool = False) -> list[Commitment]:
        """Every commitment being reserved for."""
        if self.commitment_repo is None:
            return []
        return self.commitment_repo.list_all(include_inactive=include_inactive)

    def add_commitment(self, *, commitment: Commitment) -> Commitment:
        """Store a new commitment."""
        return self.commitment_repo.add(commitment=commitment)

    def update_commitment(self, *, commitment: Commitment) -> Commitment:
        """Store changes to an existing commitment."""
        return self.commitment_repo.update(commitment=commitment)

    def end_commitment(self, *, commitment_id: int, final_month: YearMonth) -> None:
        """Stop reserving after `final_month`, keeping the months it ran in."""
        self.commitment_repo.end_from(
            commitment_id=commitment_id, final_month=final_month
        )

    def delete_commitment(self, *, commitment_id: int) -> None:
        """Remove a commitment outright."""
        self.commitment_repo.delete(commitment_id=commitment_id)

    def get_variable_spend(self) -> Amount | None:
        """Expected everyday spending a month; None while it is unset."""
        from clear_budget.application.services._settings_operations import (
            get_variable_spend_monthly_pence,
        )

        conn = getattr(self.bill_repo, "conn", None)
        stored = get_variable_spend_monthly_pence(conn)
        return None if stored is None else Amount(pence=stored)

    def build_reserve_floor(self, *, buffer_pence: int) -> ReserveFloor:
        """The commitments as a floor, standing on the caller's own buffer.

        The buffer is a parameter because this application has two of them
        and they are not the same setting: Safe to Spend keeps its own, set
        beside the overdraft, while the Reserves page carries the emergency
        buffer the Recommendations target uses. Reserves are added to
        whichever one the caller is answering for; merging the two would
        restate a figure the user has already read.
        """
        variable = self.get_variable_spend()
        return ReserveFloor(
            buffer_pence=buffer_pence,
            commitments=tuple(self.list_commitments()),
            variable_spend_monthly_pence=None if variable is None else variable.pence,
        )

    def get_reserve_floor(self) -> ReserveFloor:
        """The Reserves page's own reading: commitments over the emergency buffer."""
        enabled, buffer_amount = self.get_recommendation_buffer()
        return self.build_reserve_floor(
            buffer_pence=buffer_amount.pence if enabled else 0
        )

    def get_bank_graph_floor_values(self, *, year_month: YearMonth) -> list[int]:
        """The floor on every day of `year_month`, in pence, for the graph.

        Built on the Safe to Spend buffer rather than the Reserves page's own,
        because the graph plots the bank balance; that is the threshold Safe
        to Spend already quotes against it, so answering with the other
        buffer would draw a second, different line under the same bars.
        """
        floor = self.build_reserve_floor(
            buffer_pence=self.get_safe_to_spend_floor().pence
        )
        last = days_in_month(year_month.year, year_month.month)
        return [
            floor.at(date(year_month.year, year_month.month, day))
            for day in range(1, last + 1)
        ]

    def get_reserve_rows(self, *, today: date | None = None) -> list[ReserveRow]:
        """Every commitment with the figures the page puts in its table."""
        day = today if today is not None else date.today()  # noqa: DTZ011
        rows = []
        for commitment in self.list_commitments():
            monthly = monthly_rate_pence(commitment, day)
            natural = natural_rate_pence(commitment)
            held = accrued_pence(commitment, day)
            rows.append(
                ReserveRow(
                    commitment=commitment,
                    monthly_pence=monthly,
                    natural_pence=natural,
                    held_pence=held,
                    outstanding_pence=max(commitment.amount.pence - held, 0),
                    is_steep=monthly > natural,
                )
            )
        return rows

    def get_reserve_cost_pence(self, *, today: date | None = None) -> int:
        """How much lower Safe to Spend Today is because of the commitments.

        The line that earns the page: it connects what is being held back to
        the headline figure the user actually looks at. Never negative, since
        setting money aside cannot raise what is safe to spend.
        """
        day = today if today is not None else date.today()  # noqa: DTZ011
        with_reserves = self.get_safe_to_spend(today=day)
        without = self.get_safe_to_spend_without_reserves(today=day)
        return max(without.amount_pence - with_reserves.amount_pence, 0)

    def get_reserved_today_pence(self, *, today: date | None = None) -> int:
        """What every commitment holds back between them, right now."""
        day = today if today is not None else date.today()  # noqa: DTZ011
        return sum(reserve_pence(c, day) for c in self.list_commitments())
