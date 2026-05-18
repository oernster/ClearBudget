"""MonthGenerator — generates month bills and income from templates."""

from dataclasses import dataclass

from clear_budget.domain.entities.month_bill import MonthBill
from clear_budget.domain.entities.month_income import MonthIncome
from clear_budget.domain.interfaces.bill_repository import BillRepository
from clear_budget.domain.interfaces.income_source_repository import (
    IncomeSourceRepository,
)
from clear_budget.domain.value_objects.year_month import YearMonth


@dataclass(frozen=True, slots=True)
class MonthGenerator:
    """Service to generate a month's bills and income from templates."""

    bill_repo: BillRepository
    income_repo: IncomeSourceRepository

    def generate_month_bills(
        self,
        *,
        year_month: YearMonth,
        month_id: int,
    ) -> list[MonthBill]:
        """Generate MonthBill instances for a given month.

        Args:
            year_month: The month to generate for
            month_id: The database month ID

        Returns:
            List of MonthBill instances for this month
        """
        template_bills = self.bill_repo.list_active_for_month(year_month=year_month)
        month_bills = []

        for bill in template_bills:
            month_bill = MonthBill(
                id=0,  # Placeholder; will be assigned by repository
                month_id=month_id,
                bill_template_id=bill.id,
                name=bill.name,
                amount=bill.amount,
                payment_method_id=bill.payment_method_id,
                category=bill.category,
                day_of_month=bill.day_of_month,
                is_ad_hoc=False,
            )
            month_bills.append(month_bill)

        return month_bills

    def generate_month_income(
        self,
        *,
        year_month: YearMonth,
        month_id: int,
    ) -> list[MonthIncome]:
        """Generate MonthIncome instances for a given month.

        Args:
            year_month: The month to generate for
            month_id: The database month ID

        Returns:
            List of MonthIncome instances for this month
        """
        active_sources = self.income_repo.list_active()
        month_income = []

        for source in active_sources:
            month_inc = MonthIncome(
                id=0,  # Placeholder; will be assigned by repository
                month_id=month_id,
                income_source_id=source.id,
                name=source.name,
                amount=source.amount,
                is_reliable=source.is_reliable,
                day_of_month=source.day_of_month,
            )
            month_income.append(month_inc)

        return month_income
