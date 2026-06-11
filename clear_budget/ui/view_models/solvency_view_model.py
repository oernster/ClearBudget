"""ViewModel for solvency report display - manages financial health signals."""

from PySide6.QtCore import QObject, Signal

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.application.dto.solvency_report import SolvencyReport
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.year_month import YearMonth


class SolvencyViewModel(QObject):
    """Manages state and signals for solvency panel display."""

    solvency_updated = Signal(SolvencyReport)
    danger_warning_triggered = Signal(str)

    def __init__(
        self,
        budget_service: BudgetService,
        current_month: YearMonth | None = None,
    ) -> None:
        """Initialize solvency view model."""
        super().__init__()
        self.budget_service = budget_service
        self.current_month = current_month or YearMonth.today()
        self.current_summary: MonthSummary | None = None
        self.solvency_report: SolvencyReport | None = None
        self.refresh_solvency()

    def set_month(self, year_month: YearMonth) -> None:
        """Update month and refresh solvency report."""
        self.current_month = year_month
        self.current_summary = self.budget_service.get_month_summary(
            year_month=year_month
        )
        self.refresh_solvency()

    def update_month_summary(self, summary: MonthSummary) -> None:
        """Update solvency when month summary changes (from MonthViewModel)."""
        self.current_summary = summary
        self.refresh_solvency()

    def refresh_solvency(self) -> None:
        """Fetch and emit updated solvency report."""
        report = self.budget_service.calculate_solvency_from_summary(
            year_month=self.current_month,
            month_summary=self.current_summary,
        )
        self.solvency_report = report
        self.solvency_updated.emit(report)

        if report.balance_pence < 0:
            from clear_budget.ui.utils.format_helpers import fmt

            msg = f"Deficit: {fmt(abs(report.balance_pence))}"
            self.danger_warning_triggered.emit(msg)

    def get_status_color(self) -> str:
        """Return color code based on solvency status."""
        if not self.solvency_report:
            return "#9ca3af"
        if self.solvency_report.is_solvent:
            return "#34d399"
        return "#f87171"
