"""MonthSummary DTO  -  cross-boundary data transfer for a month's financials."""

from __future__ import annotations

from dataclasses import dataclass

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


@dataclass(frozen=True, slots=True)
class MonthSummary:
    """Summary of a month's income and expenses (application layer DTO).

    Attributes:
        year_month: The month (YYYY-MM)
        total_income: Total counted income for the month (reliable only unless
            the summary was built with assumed income included)
        total_bills: Total bills/expenses for the month (all payment methods)
        bank_bills: Total bills for bank account only (payment_method_id == 1)
        balance: total_income - bank_bills (affects bank account)
        bills: List of active bills for this month
        income_sources: Active income the figures are built from. Reliable
            only by default, so every projection in the app is money that can
            be counted on; reliable plus assumed when the summary was built
            with assumed income included.
        assumed_income_sources: Active income marked NOT reliable, whether or
            not it was counted. This is the gap specification: what has to
            actually arrive for an assumed projection to come true.
        all_income_sources: All income sources including inactive (used for display)
    """

    year_month: YearMonth
    total_income: Amount
    total_bills: Amount
    bank_bills: Amount
    balance: Amount
    bills: tuple[Bill, ...] = ()  # active only - used for calculations
    all_bills: tuple[Bill, ...] = ()  # active + inactive - used for display
    income_sources: tuple[IncomeSource, ...] = ()  # counted - used for calculations
    all_income_sources: tuple[IncomeSource, ...] = ()  # active + inactive - display
    assumed_income_sources: tuple[IncomeSource, ...] = ()  # active, not reliable

    def __str__(self) -> str:
        return (
            f"{self.year_month}: "
            f"IN={self.total_income} OUT={self.total_bills} "
            f"BALANCE={self.balance}"
        )
