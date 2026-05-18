"""Archive view widget - displays historical month data and trends."""

import csv
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
)
from PySide6.QtCore import Qt

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.widgets.archive_detail_dialog import ArchiveDetailDialog


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
        self.archive_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.archive_table.verticalHeader().setStyleSheet("QHeaderView::section { color: #34d399; }")
        self.archive_table.verticalHeader().sectionClicked.connect(self.on_row_header_click)
        layout.addWidget(self.archive_table)

        btn_layout = QHBoxLayout()
        load_btn = QPushButton("Load Last 12 Months")
        export_btn = QPushButton("Export CSV")
        btn_layout.addWidget(load_btn)
        btn_layout.addWidget(export_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        load_btn.clicked.connect(self.on_load_history)
        export_btn.clicked.connect(self.on_export_csv)
        self.months_by_row = {}

    def on_row_header_click(self, row: int) -> None:
        """Handle pencil icon click on row header to show details."""
        if row in self.months_by_row:
            month, summary = self.months_by_row[row]
            dialog = ArchiveDetailDialog(self, month, summary)
            dialog.exec()

    def on_load_history(self) -> None:
        """Load recorded months from database."""
        recorded_months = self.budget_service.get_recorded_months()
        self.load_history(recorded_months)

    def on_export_csv(self) -> None:
        """Export archive data to CSV with detailed bills and income."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Archive", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        recorded_months = self.budget_service.get_recorded_months()
        try:
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                for month in recorded_months:
                    summary = self.budget_service.get_month_summary(year_month=month)
                    status = "Solvent" if summary.balance.pence >= 0 else "Deficit"

                    # Month header
                    writer.writerow([f"Month: {month}"])
                    writer.writerow([])

                    # Summary
                    writer.writerow(["Summary"])
                    writer.writerow([
                        "Income",
                        f"{summary.total_income.pounds:.2f}",
                    ])
                    writer.writerow([
                        "Total Bills",
                        f"{summary.total_bills.pounds:.2f}",
                    ])
                    writer.writerow([
                        "Balance",
                        f"{summary.balance.pounds:.2f}",
                    ])
                    writer.writerow([
                        "Status",
                        status,
                    ])
                    writer.writerow([])

                    # Bills section
                    writer.writerow(["Bills"])
                    writer.writerow(["Name", "Amount", "Category", "Payment Method", "Due Day", "Active"])
                    for bill in summary.bills:
                        writer.writerow([
                            bill.name,
                            f"{bill.amount.pounds:.2f}",
                            bill.category,
                            bill.payment_method_id,
                            bill.day_of_month or "~",
                            "Yes" if bill.active else "No",
                        ])
                    writer.writerow([])

                    # Income section
                    writer.writerow(["Income"])
                    writer.writerow(["Name", "Amount", "Reliable", "Due Day", "Active"])
                    for income in summary.income_sources:
                        writer.writerow([
                            income.name,
                            f"{income.amount.pounds:.2f}",
                            "Yes" if income.is_reliable else "No",
                            income.day_of_month or "~",
                            "Yes" if income.active else "No",
                        ])
                    writer.writerow([])
                    writer.writerow([])
        except IOError:
            pass

    def load_history(self, months: list[YearMonth]) -> None:
        """Load historical months into table."""
        self.archive_table.setRowCount(0)
        self.months_by_row = {}

        for month in months:
            summary = self.budget_service.get_month_summary(year_month=month)

            row = self.archive_table.rowCount()
            self.archive_table.insertRow(row)
            self.archive_table.setVerticalHeaderItem(row, QTableWidgetItem("📝"))
            self.months_by_row[row] = (month, summary)

            self.archive_table.setItem(row, 0, QTableWidgetItem(str(month)))
            self.archive_table.setItem(row, 1, QTableWidgetItem(str(summary.total_income)))
            self.archive_table.setItem(row, 2, QTableWidgetItem(str(summary.total_bills)))
            self.archive_table.setItem(row, 3, QTableWidgetItem(str(summary.balance)))

            status = "✓ Solvent" if summary.balance.pence >= 0 else "✗ Deficit"
            self.archive_table.setItem(row, 4, QTableWidgetItem(status))
