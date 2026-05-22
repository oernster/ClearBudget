"""Month mapper helpers - convert domain entities to month-bill/income DTOs.

Extracted from BudgetService to stay under LOC limit.
"""

from clear_budget.domain.entities.month_bill import MonthBill
from clear_budget.domain.entities.month_income import MonthIncome


def bills_to_month_bills(bills, month_id: int) -> list[MonthBill]:  # pragma: no cover
    return [
        MonthBill(
            id=bill.id,
            month_id=month_id,
            bill_template_id=bill.id,
            name=bill.name,
            amount=bill.amount,
            payment_method_id=bill.payment_method_id,
            category=bill.category,
            day_of_month=bill.day_of_month,
            is_ad_hoc=False,
        )
        for bill in bills
    ]


def income_to_month_income(
    income_sources, month_id: int
) -> list[MonthIncome]:  # pragma: no cover
    return [
        MonthIncome(
            id=inc.id,
            month_id=month_id,
            income_source_id=inc.id,
            name=inc.name,
            amount=inc.amount,
            is_reliable=inc.is_reliable,
            day_of_month=inc.day_of_month,
        )
        for inc in income_sources
    ]
