"""Dialog for viewing archived month details."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
)
from PySide6.QtCore import Qt

from clear_budget.domain.value_objects.year_month import YearMonth


class ArchiveDetailDialog(QDialog):
    """Dialog showing detailed view of an archived month."""

    def __init__(self, parent=None, year_month: YearMonth = None, summary=None) -> None:
        """Initialize archive detail dialog."""
        super().__init__(parent)
        self.year_month = year_month
        self.summary = summary
        self.setWindowTitle(f"Archive Details - {year_month}")
        self.setGeometry(100, 100, 700, 600)
        self.setModal(True)
        self.init_ui()

    def init_ui(self) -> None:
        """Build dialog layout."""
        layout = QVBoxLayout()

        # Header info
        header_layout = QHBoxLayout()
        month_label = QLabel(f"<b>{self.year_month}</b>")
        month_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(month_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Summary info
        if self.summary:
            summary_text = (
                f"Income: {self.summary.total_income} | "
                f"Bills: {self.summary.total_bills} | "
                f"Balance: {self.summary.balance}"
            )
            summary_label = QLabel(summary_text)
            summary_label.setStyleSheet("font-size: 17px; color: #888;")
            layout.addWidget(summary_label)

        # Bills table
        bills_label = QLabel("Bills")
        bills_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(bills_label)

        bills_table = QTableWidget()
        bills_table.setColumnCount(5)
        bills_table.setHorizontalHeaderLabels(["Name", "Amount", "Category", "Payment Method", "Due Day"])
        bills_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(bills_table)

        # Populate bills
        if self.summary:
            bills_table.setRowCount(len(self.summary.bills))
            for row, bill in enumerate(self.summary.bills):
                bills_table.setItem(row, 0, QTableWidgetItem(bill.name))
                bills_table.setItem(row, 1, QTableWidgetItem(str(bill.amount)))
                bills_table.setItem(row, 2, QTableWidgetItem(bill.category))
                bills_table.setItem(row, 3, QTableWidgetItem(str(bill.payment_method_id)))
                bills_table.setItem(row, 4, QTableWidgetItem(str(bill.day_of_month) if bill.day_of_month else "~"))

        # Income table
        income_label = QLabel("Income")
        income_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(income_label)

        income_table = QTableWidget()
        income_table.setColumnCount(4)
        income_table.setHorizontalHeaderLabels(["Name", "Amount", "Reliable", "Due Day"])
        income_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(income_table)

        # Populate income
        if self.summary:
            income_table.setRowCount(len(self.summary.income_sources))
            for row, income in enumerate(self.summary.income_sources):
                income_table.setItem(row, 0, QTableWidgetItem(income.name))
                income_table.setItem(row, 1, QTableWidgetItem(str(income.amount)))
                income_table.setItem(row, 2, QTableWidgetItem("✓" if income.is_reliable else "✗"))
                income_table.setItem(row, 3, QTableWidgetItem(str(income.day_of_month) if income.day_of_month else "~"))

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)
