"""Archive view widget - displays historical month data and trends."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)
from PySide6.QtCore import Qt

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.year_month import YearMonth


class ArchiveView(QWidget):
    """Displays historical month summaries and solvency trends."""

    def __init__(self, budget_service: BudgetService) -> None:
        """Initialize archive view widget."""
        super().__init__()
        self.budget_service = budget_service
        self.init_ui()

    def init_ui(self) -> None:
        """Build archive view layout."""
        layout = QVBoxLayout()

        self.archive_table = QTableWidget()
        self.archive_table.setColumnCount(5)
        self.archive_table.setHorizontalHeaderLabels(
            ["Month", "Income", "Bills", "Balance", "Status"]
        )
        layout.addWidget(self.archive_table)

        btn_layout = QHBoxLayout()
        load_btn = QPushButton("Load Last 12 Months")
        export_btn = QPushButton("Export CSV")
        btn_layout.addWidget(load_btn)
        btn_layout.addWidget(export_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        load_btn.clicked.connect(self.on_load_history)

    def on_load_history(self) -> None:
        """Load last 12 months of history."""
        current = YearMonth(2026, 5)
        start_month = current.previous_month().previous_month().previous_month()
        start_month = start_month.previous_month().previous_month().previous_month()
        start_month = start_month.previous_month().previous_month().previous_month()
        start_month = start_month.previous_month().previous_month().previous_month()
        self.load_history(start_month, current)

    def load_history(self, start_month: YearMonth, end_month: YearMonth) -> None:
        """Load historical months into table."""
        self.archive_table.setRowCount(0)

        current = start_month
        while current <= end_month:
            summary = self.budget_service.get_month_summary(year_month=current)

            row = self.archive_table.rowCount()
            self.archive_table.insertRow(row)

            self.archive_table.setItem(row, 0, QTableWidgetItem(str(current)))
            self.archive_table.setItem(row, 1, QTableWidgetItem(str(summary.total_income)))
            self.archive_table.setItem(row, 2, QTableWidgetItem(str(summary.total_bills)))
            self.archive_table.setItem(row, 3, QTableWidgetItem(str(summary.balance)))

            status = "✓ Solvent" if summary.balance.pence >= 0 else "✗ Deficit"
            self.archive_table.setItem(row, 4, QTableWidgetItem(status))

            current = current.next_month()
