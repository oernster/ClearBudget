"""BillAmountChange value object: a bill's amount changing from a given month.

The worked case is a rent increase. The same bill costs one amount up to a
month and another from that month on, and the report for an earlier month must
still show what it actually cost then.

Month granularity, not day: a bill belongs to a month in this application, so a
change that took effect mid-month still applies to that month as a whole. This
is the one deliberate difference from `CreditLimitChange`, which carries a day
because a card's limit genuinely moves on a date.
"""

from __future__ import annotations

from dataclasses import dataclass

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.shared.errors import InvalidBillAmountChangeError

_MIN_MONTH = 1
_MAX_MONTH = 12


@dataclass(frozen=True, slots=True)
class BillAmountChange:
    """The amount a bill takes from `effective_year`/`effective_month` onward.

    Attributes:
        effective_year / effective_month: the first month the new amount applies
        new_amount: the amount that applies from that month onward
    """

    effective_year: int
    effective_month: int
    new_amount: Amount

    def __post_init__(self) -> None:
        if not _MIN_MONTH <= self.effective_month <= _MAX_MONTH:
            raise InvalidBillAmountChangeError(
                f"Month must be {_MIN_MONTH}-{_MAX_MONTH}, "
                f"got {self.effective_month}"
            )

    @property
    def sort_key(self) -> tuple[int, int]:
        """Ordering key by effective month."""
        return (self.effective_year, self.effective_month)
