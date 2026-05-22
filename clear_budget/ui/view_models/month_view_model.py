"""ViewModel for month budget view - manages UI state and signals."""

from PySide6.QtCore import QObject, Signal

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.year_month import YearMonth


class MonthViewModel(QObject):
    """Manages state and signals for month budget display."""

    month_changed = Signal(YearMonth)
    month_summary_updated = Signal(MonthSummary)

    def __init__(
        self,
        budget_service: BudgetService,
        current_month: YearMonth = YearMonth(2026, 5),
    ) -> None:
        """Initialize month view model."""
        from datetime import datetime

        super().__init__()
        self.budget_service = budget_service
        self.current_month = current_month
        self.base_month = YearMonth(datetime.now().year, datetime.now().month)
        self.today = datetime.now().date()
        self.month_summary: MonthSummary | None = None
        self.refresh_month_summary()

    def set_month(self, year_month: YearMonth) -> None:
        """Change current month and refresh summary."""
        self.current_month = year_month
        self.month_changed.emit(year_month)
        self.refresh_month_summary()

    def next_month(self) -> None:
        """Move to next month."""
        next_ym = self.current_month.next_month()
        self.set_month(next_ym)

    def previous_month(self) -> None:
        """Move to previous month."""
        prev_ym = self.current_month.previous_month()
        self.set_month(prev_ym)

    def refresh_month_summary(self) -> None:
        """Fetch and emit updated month summary."""
        summary = self.budget_service.get_month_summary(year_month=self.current_month)
        self.month_summary = summary
        self.month_summary_updated.emit(summary)

    def add_bill(self, *, bill: Bill) -> None:
        """Create a new bill and refresh summary."""
        self.budget_service.add_bill(bill=bill)
        self.refresh_month_summary()

    def update_bill(self, *, bill: Bill) -> None:
        """Update an existing bill and refresh summary."""
        self.budget_service.update_bill(bill=bill)
        self.refresh_month_summary()

    def update_bill_for_month(self, *, bill: Bill) -> None:
        """Store per-month override for a bill and refresh summary."""
        self.budget_service.update_bill_for_month(
            bill=bill, year_month=self.current_month
        )
        self.refresh_month_summary()

    def delete_bill(self, *, bill_id: int) -> None:
        """Delete a bill and refresh summary."""
        self.budget_service.delete_bill(bill_id=bill_id)
        self.refresh_month_summary()

    def delete_bills(self, *, bill_ids: list[int]) -> None:
        """Delete multiple bills in one batch then refresh once."""
        for bill_id in bill_ids:
            self.budget_service.delete_bill(bill_id=bill_id)
        self.refresh_month_summary()

    def set_bill_active(self, *, bill_id: int, active: bool) -> None:
        """Toggle bill active state and refresh summary."""
        self.budget_service.set_bill_active(bill_id=bill_id, active=active)
        self.refresh_month_summary()

    def delete_bill_month_override(self, *, bill_id: int) -> None:
        """Remove the month-only override for a bill, reverting to template."""
        self.budget_service.delete_bill_month_override(
            bill_id=bill_id, year_month=self.current_month
        )
        self.refresh_month_summary()

    def skip_bill_for_month(self, *, bill_id: int) -> None:
        """Exclude a bill from the current month's calculations only."""
        self.budget_service.skip_bill_for_month(
            bill_id=bill_id, year_month=self.current_month
        )
        self.refresh_month_summary()

    def unskip_bill_for_month(self, *, bill_id: int) -> None:
        """Restore a bill to the current month's calculations."""
        self.budget_service.unskip_bill_for_month(
            bill_id=bill_id, year_month=self.current_month
        )
        self.refresh_month_summary()

    def add_income(self, *, income) -> None:
        """Create a new income source and refresh summary."""
        self.budget_service.add_income(income=income)
        self.refresh_month_summary()

    def update_income(self, *, income) -> None:
        """Update an existing income source and refresh summary."""
        self.budget_service.update_income(income=income)
        self.refresh_month_summary()

    def delete_income(self, *, income_id: int) -> None:
        """Delete an income source and refresh summary."""
        self.budget_service.delete_income(income_id=income_id)
        self.refresh_month_summary()

    def delete_incomes(self, *, income_ids: list[int]) -> None:
        """Delete multiple income sources in one batch then refresh once."""
        for income_id in income_ids:
            self.budget_service.delete_income(income_id=income_id)
        self.refresh_month_summary()
