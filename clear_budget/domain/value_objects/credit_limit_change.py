"""CreditLimitChange value object - a scheduled change to a card's credit limit."""

from __future__ import annotations

import calendar
from dataclasses import dataclass

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.shared.errors import InvalidCreditLimitChangeError

_MIN_MONTH = 1
_MAX_MONTH = 12
_MIN_DAY = 1


@dataclass(frozen=True, slots=True)
class CreditLimitChange:
    """A scheduled change to a credit card's limit, effective on a given date.

    Attributes:
        effective_year / effective_month / effective_day: when the new limit
            takes effect
        new_limit: the limit that applies from the effective date onward
    """

    effective_year: int
    effective_month: int
    effective_day: int
    new_limit: Amount

    def __post_init__(self) -> None:
        """Validate the effective date is a real calendar date."""
        if not _MIN_MONTH <= self.effective_month <= _MAX_MONTH:
            raise InvalidCreditLimitChangeError(
                f"Month must be {_MIN_MONTH}-{_MAX_MONTH}, got {self.effective_month}"
            )
        days_in_month = calendar.monthrange(self.effective_year, self.effective_month)[
            1
        ]
        if not _MIN_DAY <= self.effective_day <= days_in_month:
            raise InvalidCreditLimitChangeError(
                f"Day must be {_MIN_DAY}-{days_in_month} for "
                f"{self.effective_year}-{self.effective_month:02d}, "
                f"got {self.effective_day}"
            )

    @property
    def sort_key(self) -> tuple[int, int, int]:
        """Ordering key by effective date (year, month, day)."""
        return (self.effective_year, self.effective_month, self.effective_day)
