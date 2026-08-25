"""IncomeSource entity  -  a recurring income stream."""

from dataclasses import dataclass

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


@dataclass(frozen=True, slots=True)
class IncomeSource:
    """A source of income (e.g., Universal Credit, M+D Loan).

    Attributes:
        id: Unique identifier
        name: Human-readable name
        amount: Monthly amount
        is_reliable: Whether to use this in forward solvency projections
        day_of_month: Expected arrival day (e.g., 1st, 21st)
        active: Whether currently receiving this income
        start_ym: First month this income appears (None = it always has)
        end_ym: Last month this income appears (None = it continues)
        is_month_only: Whether this is a one-off entry for a single month
        skipped_for_month: Whether this income is skipped for the queried month
        has_month_override: Whether this income has a per-month override
        received_for_month: Whether marked received for the queried month
    """

    id: int
    name: str
    amount: Amount
    is_reliable: bool
    day_of_month: int | None
    active: bool = True
    # Both bounds are nullable and both nulls mean "unbounded in that
    # direction". A bill makes its start month mandatory; income cannot,
    # because every row that existed before these columns did has no start to
    # record; inventing one would rewrite the months it already appeared
    # in. Unbounded is the only honest reading of "not stated".
    start_ym: YearMonth | None = None
    end_ym: YearMonth | None = None
    is_month_only: bool = False
    skipped_for_month: bool = False
    has_month_override: bool = False
    received_for_month: bool = False
    # Whether the arrival day is fixed in the real world (a benefit payment
    # date, an employer's payroll run). Records the EXCEPTION, so the default
    # is movable; the Recommendations engine proposes retiming only what can
    # move.
    day_fixed: bool = False

    def is_active_in_month(self, year_month: YearMonth) -> bool:
        """Whether this income appears in the given month.

        Mirrors Bill.is_active_in_month, so a month decides what it contains
        the same way on both sides of the ledger.
        """
        if not self.active:
            return False
        if self.start_ym is not None and year_month < self.start_ym:
            return False
        return self.end_ym is None or year_month <= self.end_ym

    def __str__(self) -> str:
        reliable = "[reliable]" if self.is_reliable else "[variable]"
        return f"{self.name} {self.amount} {reliable}"
