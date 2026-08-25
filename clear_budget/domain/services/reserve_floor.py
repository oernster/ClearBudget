"""The floor  -  the balance the projection refuses to call spendable.

This replaces the scalar emergency buffer everywhere the projection used one.
The buffer was a single number that meant the same thing on every day of every
month; the floor is a function of the day, because what a budget has to keep
back genuinely varies: an annual bill four months out is holding back more of
today's balance each month it gets closer.

Pure and deterministic: a floor built from the same commitments answers the
same for the same day, whatever the clock says. A floor built with no
commitments and no everyday spending answers the buffer for every day, which
is what lets an existing budget project bit-identically after the migration.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from clear_budget.domain.entities.commitment import Commitment
from clear_budget.domain.services.reserve_accrual import reserve_pence


@dataclass(frozen=True, slots=True)
class ReserveFloor:
    """What must stay in the account, day by day.

    Attributes:
        buffer_pence: The emergency buffer, held on every day alike
        commitments: Everything being reserved for
        variable_spend_monthly_pence: What the user expects everyday spending
            to cost this month; None while unset, which is the phase-one
            state and is reported in words rather than assumed to be zero
    """

    buffer_pence: int
    commitments: tuple[Commitment, ...] = ()
    variable_spend_monthly_pence: int | None = None

    @classmethod
    def flat(cls, buffer_pence: int) -> "ReserveFloor":
        """A floor that is the buffer and nothing else, on every day.

        The shape every budget has before it sets anything aside; the one
        the projection had before this existed.
        """
        return cls(buffer_pence=buffer_pence)

    def at(self, day: date) -> int:
        """The floor on `day`, in pence."""
        total = self.buffer_pence
        for commitment in self.commitments:
            total += reserve_pence(commitment, day)
        return total + self.variable_pence_at(day)

    def reserved_at(self, day: date) -> int:
        """What the commitments alone hold back on `day`, without the buffer."""
        return sum(reserve_pence(c, day) for c in self.commitments)

    def variable_pence_at(self, day: date) -> int:
        """The everyday-spending hold-back on `day`.

        A burn-down rather than a flat figure: what is held is the spending
        the rest of the month still has to cover, so it falls as the month is
        used up. Today counts as still to come, because today's shopping has
        not happened yet.
        """
        monthly = self.variable_spend_monthly_pence
        if not monthly:
            return 0
        days_in_month = calendar.monthrange(day.year, day.month)[1]
        remaining = days_in_month - day.day + 1
        return (monthly * remaining) // days_in_month

    @property
    def is_flat(self) -> bool:
        """Whether this floor is the plain buffer on every day."""
        return not self.commitments and not self.variable_spend_monthly_pence
