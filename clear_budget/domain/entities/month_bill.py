"""MonthBill entity  -  a bill entry for a specific month."""

from dataclasses import dataclass

from clear_budget.domain.value_objects.amount import Amount


@dataclass(frozen=True, slots=True)
class MonthBill:
    """A bill instantiated for a specific month.

    Can override template amount, can be ad-hoc (not from template).

    Attributes:
        id: Unique identifier
        month_id: Which month (FK to Month)
        bill_template_id: Which template this came from (None if ad-hoc)
        name: Bill name (from template or custom)
        amount: Actual amount for this month (may override template)
        payment_method_id: Which account/card to debit
        category: Bill category
        day_of_month: Day due (None if flexible)
        is_ad_hoc: True if created directly, not from template
    """

    id: int
    month_id: int
    bill_template_id: int | None
    name: str
    amount: Amount
    payment_method_id: int
    category: str
    day_of_month: int | None
    is_ad_hoc: bool = False

    def __str__(self) -> str:
        template = "(ad-hoc)" if self.is_ad_hoc else ""
        return f"{self.name} {self.amount} {template}".strip()
