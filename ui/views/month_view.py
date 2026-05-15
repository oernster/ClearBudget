from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox
)
from PySide6.QtCore import Qt
from datetime import datetime
from models.month import Month
from services.solvency_calculator import SolvencyCalculator

class MonthView(QWidget):
    def __init__(self, db, year_month, on_month_changed=None):
        super().__init__()
        self.db = db
        self.year_month = year_month
        self.on_month_changed = on_month_changed

        layout = QVBoxLayout()

        # Month navigation
        nav_layout = QHBoxLayout()
        nav_layout.addStretch()

        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.clicked.connect(self._prev_month)
        nav_layout.addWidget(self.prev_btn)

        self.month_label = QLabel(year_month)
        self.month_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        nav_layout.addWidget(self.month_label)

        self.next_btn = QPushButton("Next →")
        self.next_btn.clicked.connect(self._next_month)
        nav_layout.addWidget(self.next_btn)

        layout.addLayout(nav_layout)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()

        # Income section
        scroll_layout.addWidget(self._build_income_section())

        # Bills section (by category)
        scroll_layout.addWidget(self._build_bills_section())

        # Totals
        self.totals_label = QLabel("")
        self.totals_label.setStyleSheet("font-size: 12px; font-weight: bold; padding: 10px;")
        scroll_layout.addWidget(self.totals_label)

        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)

        layout.addWidget(scroll)

        # Archive button
        archive_btn = QPushButton("Archive This Month")
        archive_btn.clicked.connect(self._archive_month)
        layout.addWidget(archive_btn)

        self.setLayout(layout)
        self._refresh()

    def _build_income_section(self):
        """Build income table."""
        group = QGroupBox("Income")
        layout = QVBoxLayout()

        self.income_table = QTableWidget()
        self.income_table.setColumnCount(3)
        self.income_table.setHorizontalHeaderLabels(["Name", "Amount", "Day"])
        self.income_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        layout.addWidget(self.income_table)
        group.setLayout(layout)
        return group

    def _build_bills_section(self):
        """Build bills grouped by category."""
        group = QGroupBox("Bills")
        layout = QVBoxLayout()

        self.bills_table = QTableWidget()
        self.bills_table.setColumnCount(4)
        self.bills_table.setHorizontalHeaderLabels(["Name", "Amount", "Day", "Method"])
        self.bills_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        layout.addWidget(self.bills_table)
        group.setLayout(layout)
        return group

    def _refresh(self):
        """Refresh month data."""
        month_data = Month.get_month_data(self.db, self.year_month)

        # Fill income table
        self.income_table.setRowCount(len(month_data['income']))
        total_income = 0
        for row, inc in enumerate(month_data['income']):
            self.income_table.setItem(row, 0, QTableWidgetItem(inc['name']))
            self.income_table.setItem(row, 1, QTableWidgetItem(f"£{inc['amount']:.2f}"))
            day = inc['day_of_month'] or "—"
            self.income_table.setItem(row, 2, QTableWidgetItem(str(day)))
            total_income += inc['amount']

        # Fill bills table
        self.bills_table.setRowCount(len(month_data['bills']))
        total_bills = 0
        for row, bill in enumerate(month_data['bills']):
            self.bills_table.setItem(row, 0, QTableWidgetItem(bill['name']))
            self.bills_table.setItem(row, 1, QTableWidgetItem(f"£{bill['amount']:.2f}"))
            day = bill['day_of_month'] or "—"
            self.bills_table.setItem(row, 2, QTableWidgetItem(str(day)))

            # Get payment method name
            cursor = self.db.execute('SELECT name FROM payment_methods WHERE id = ?', (bill['payment_method_id'],))
            pm_name = cursor.fetchone()['name']
            self.bills_table.setItem(row, 3, QTableWidgetItem(pm_name))

            total_bills += bill['amount']

        # Update totals
        balance = total_income - total_bills
        color = "green" if balance >= 0 else "red"
        self.totals_label.setText(f"Income: £{total_income:.2f} | Bills: £{total_bills:.2f} | Balance: £{balance:.2f}")
        self.totals_label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 10px;")

    def _prev_month(self):
        """Go to previous month."""
        year, month = map(int, self.year_month.split('-'))
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        self.year_month = f"{year:04d}-{month:02d}"
        self.month_label.setText(self.year_month)
        self._refresh()
        if self.on_month_changed:
            self.on_month_changed(self.year_month)

    def _next_month(self):
        """Go to next month."""
        year, month = map(int, self.year_month.split('-'))
        month += 1
        if month > 12:
            month = 1
            year += 1
        self.year_month = f"{year:04d}-{month:02d}"
        self.month_label.setText(self.year_month)
        self._refresh()
        if self.on_month_changed:
            self.on_month_changed(self.year_month)

    def _archive_month(self):
        """Archive current month."""
        Month.archive(self.db, self.year_month)
        self._next_month()

    def update_month(self, year_month):
        """External update."""
        self.year_month = year_month
        self.month_label.setText(year_month)
        self._refresh()
