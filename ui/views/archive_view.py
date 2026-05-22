from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
)
from models.month import Month


class ArchiveView(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db

        layout = QVBoxLayout()

        # Archived months table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Month", "Total Income", "Total Bills", "Balance"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        layout.addWidget(self.table)

        # Restore button
        restore_btn = QPushButton("Restore Selected Month")
        restore_btn.clicked.connect(self._restore_month)
        layout.addWidget(restore_btn)

        self.setLayout(layout)
        self._refresh()

    def _refresh(self):
        """Refresh archived months."""
        archived = Month.list_months(self.db, archived=True)
        self.table.setRowCount(len(archived))

        for row, ym in enumerate(archived):
            month_data = Month.get_month_data(self.db, ym)
            total_income = sum(i["amount"] for i in month_data["income"])
            total_bills = sum(b["amount"] for b in month_data["bills"])
            balance = total_income - total_bills

            self.table.setItem(row, 0, QTableWidgetItem(ym))
            self.table.setItem(row, 1, QTableWidgetItem(f"£{total_income:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"£{total_bills:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"£{balance:.2f}"))

    def _restore_month(self):
        """Restore selected month."""
        current_row = self.table.currentRow()
        if current_row >= 0:
            ym = self.table.item(current_row, 0).text()
            Month.unarchive(self.db, ym)
            self._refresh()
