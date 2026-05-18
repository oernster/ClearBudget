"""Month budget view widget - displays bills and income for selected month."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent

from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.widgets.bill_dialog import BillDialog
from clear_budget.ui.widgets.income_dialog import IncomeDialog
from clear_budget.ui.widgets.balance_dialog import BalanceDialog


class ClickableLabel(QLabel):
    """QLabel that emits clicked signal on mouse press."""
    clicked = Signal()
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit clicked signal on mouse press."""
        self.clicked.emit()
        super().mousePressEvent(event)

class MonthView(QWidget):
    """Displays bills and income for current month in tabular form."""

    @staticmethod
    def _format_category(category: str) -> str:
        """Format category: replace underscores with spaces and capitalize."""
        # Singular form mappings
        singular_map = {
            "subscriptions": "subscription",
            "utilities": "utility",
        }
        formatted = singular_map.get(category, category)
        return formatted.replace("_", " ").title()

    def __init__(self, view_model: MonthViewModel) -> None:
        """Initialize month view widget."""
        super().__init__()
        self.view_model = view_model
        self.add_bill_btn = None
        self.edit_bill_btn = None
        self.delete_bill_btn = None
        self.add_income_btn = None
        self.edit_income_btn = None
        self.delete_income_btn = None
        self.month_label = None
        self.bills_sort_column = 4  # Default: sort by "Due" column
        self.bills_sort_ascending = True
        self.income_sort_column = 0  # Default: sort by "Name" column
        self.income_sort_ascending = True
        self.init_ui()
        self.connect_signals()
        self.view_model.refresh_month_summary()

    def init_ui(self) -> None:
        """Build month view layout."""
        layout = QVBoxLayout()

        # Month display (VERY prominent)
        header_layout = QVBoxLayout()

        nav_layout = QHBoxLayout()
        prev_btn = QPushButton("← Previous")
        next_btn = QPushButton("Next →")
        nav_layout.addWidget(prev_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(next_btn)
        header_layout.addLayout(nav_layout)

        # Create a HUGE month label
        month_names = ["", "January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]
        month_str = f"{month_names[self.view_model.current_month.month]} {self.view_model.current_month.year}"
        self.month_label = QLabel(month_str)
        self.month_label.setStyleSheet(
            "font-size: 36px; font-weight: bold; padding: 20px; "
            "background-color: #1a1a2e; color: #00d4ff; text-align: center; border-radius: 8px;"
        )
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.month_label)

        # Summary info (Income, Bills, Balance)
        summary_layout = QHBoxLayout()
        self.income_label = QLabel("Income: £0.00")
        self.income_label.setStyleSheet("font-size: 14px; padding: 5px;")
        self.bills_label = QLabel("Bills: £0.00")
        self.bills_label.setStyleSheet("font-size: 14px; padding: 5px;")

        # Pencil button for editing balance (LEFT of balance label)
        self.edit_balance_btn = QPushButton("✏")
        self.edit_balance_btn.setMaximumWidth(28)
        self.edit_balance_btn.setMaximumHeight(22)
        self.edit_balance_btn.setStyleSheet(
            "QPushButton { border: none; background-color: transparent; color: #34d399; font-size: 14px; padding: 0px; }"
            "QPushButton:hover { background-color: #1a1a2e; border-radius: 3px; }"
        )

        self.balance_label = QLabel("Balance: £0.00")
        self.balance_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #34d399; padding: 5px;"
        )

        summary_layout.addWidget(self.income_label)
        summary_layout.addWidget(self.bills_label)
        summary_layout.addStretch()
        summary_layout.addWidget(self.edit_balance_btn)
        summary_layout.addWidget(self.balance_label)
        header_layout.addLayout(summary_layout)

        layout.addLayout(header_layout)

        bills_group = QGroupBox("Bills")
        bills_layout = QVBoxLayout()

        self.bills_table = QTableWidget()
        self.bills_table.setColumnCount(6)
        self.bills_table.setHorizontalHeaderLabels(
            ["Name", "Amount", "Category", "Payment Method", "Due", "Active"]
        )
        self.bills_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bills_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.bills_table.setColumnWidth(0, 120)  # Name
        self.bills_table.setColumnWidth(1, 100)  # Amount
        self.bills_table.setColumnWidth(2, 130)  # Category
        self.bills_table.setColumnWidth(3, 140)  # Payment Method
        self.bills_table.setColumnWidth(4, 80)   # Due
        self.bills_table.setColumnWidth(5, 70)   # Active
        self.bills_table.horizontalHeader().sectionClicked.connect(self.on_bills_header_click)
        bills_layout.addWidget(self.bills_table)

        bills_btn_layout = QHBoxLayout()
        self.add_bill_btn = QPushButton("Add Bill")
        self.edit_bill_btn = QPushButton("Edit Bill")
        self.delete_bill_btn = QPushButton("Delete Bill")
        bills_btn_layout.addWidget(self.add_bill_btn)
        bills_btn_layout.addWidget(self.edit_bill_btn)
        bills_btn_layout.addWidget(self.delete_bill_btn)
        bills_layout.addLayout(bills_btn_layout)

        bills_group.setLayout(bills_layout)
        layout.addWidget(bills_group)

        income_group = QGroupBox("Income")
        income_layout = QVBoxLayout()

        self.income_table = QTableWidget()
        self.income_table.setColumnCount(4)
        self.income_table.setHorizontalHeaderLabels(
            ["Name", "Amount", "Reliable", "Active"]
        )
        self.income_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.income_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.income_table.horizontalHeader().sectionClicked.connect(self.on_income_header_click)
        income_layout.addWidget(self.income_table)

        income_btn_layout = QHBoxLayout()
        self.add_income_btn = QPushButton("Add Income")
        self.edit_income_btn = QPushButton("Edit Income")
        self.delete_income_btn = QPushButton("Delete Income")
        income_btn_layout.addWidget(self.add_income_btn)
        income_btn_layout.addWidget(self.edit_income_btn)
        income_btn_layout.addWidget(self.delete_income_btn)
        income_layout.addLayout(income_btn_layout)

        income_group.setLayout(income_layout)
        layout.addWidget(income_group)

        self.setLayout(layout)

        prev_btn.clicked.connect(self.view_model.previous_month)
        next_btn.clicked.connect(self.view_model.next_month)
        self.edit_balance_btn.clicked.connect(self.on_edit_balance)
        self.add_bill_btn.clicked.connect(self.on_add_bill)
        self.edit_bill_btn.clicked.connect(self.on_edit_bill)
        self.delete_bill_btn.clicked.connect(self.on_delete_bill)
        self.add_income_btn.clicked.connect(self.on_add_income)
        self.edit_income_btn.clicked.connect(self.on_edit_income)
        self.delete_income_btn.clicked.connect(self.on_delete_income)

    def connect_signals(self) -> None:
        """Connect ViewModel signals to view updates."""
        self.view_model.month_summary_updated.connect(self.update_bills_table)
        self.view_model.month_changed.connect(self._update_month_label)

    def _update_month_label(self, year_month) -> None:
        """Update month label when month changes."""
        month_names = ["", "January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]
        month_str = f"{month_names[year_month.month]} {year_month.year}"
        self.month_label.setText(month_str)
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def on_bills_header_click(self, logical_index: int) -> None:
        """Handle bill table header click for sorting."""
        if self.bills_sort_column == logical_index:
            self.bills_sort_ascending = not self.bills_sort_ascending
        else:
            self.bills_sort_column = logical_index
            self.bills_sort_ascending = True
        self.view_model.refresh_month_summary()

    def on_income_header_click(self, logical_index: int) -> None:
        """Handle income table header click for sorting."""
        if self.income_sort_column == logical_index:
            self.income_sort_ascending = not self.income_sort_ascending
        else:
            self.income_sort_column = logical_index
            self.income_sort_ascending = True
        self.view_model.refresh_month_summary()

    def _sort_bills(self, bills) -> list:
        """Sort bills based on current sort settings."""
        # Column indices: 0=Name, 1=Amount, 2=Category, 3=Payment Method, 4=Due, 5=Active
        if self.bills_sort_column == 0:  # Name
            key_fn = lambda b: b.name.lower()
        elif self.bills_sort_column == 1:  # Amount
            key_fn = lambda b: b.amount.pence
        elif self.bills_sort_column == 2:  # Category
            key_fn = lambda b: b.category.lower()
        elif self.bills_sort_column == 3:  # Payment Method
            key_fn = lambda b: b.payment_method_id
        elif self.bills_sort_column == 4:  # Due
            key_fn = lambda b: b.day_of_month or 99
        else:  # Active (5)
            key_fn = lambda b: not b.active

        sorted_bills = sorted(bills, key=key_fn, reverse=not self.bills_sort_ascending)
        return sorted_bills

    def _sort_income(self, income_sources) -> list:
        """Sort income sources based on current sort settings."""
        # Column indices: 0=Name, 1=Amount, 2=Reliable, 3=Active
        if self.income_sort_column == 0:  # Name
            key_fn = lambda i: i.name.lower()
        elif self.income_sort_column == 1:  # Amount
            key_fn = lambda i: i.amount.pence
        elif self.income_sort_column == 2:  # Reliable
            key_fn = lambda i: not i.is_reliable
        else:  # Active (3)
            key_fn = lambda i: not i.active

        sorted_income = sorted(income_sources, key=key_fn, reverse=not self.income_sort_ascending)
        return sorted_income

    def _get_balance_color(self, balance_pence: int) -> str:
        """Get color for balance display."""
        if balance_pence < 0:
            return "#f87171"  # Red
        if balance_pence < 10000:  # Less than £100
            return "#fbbf24"  # Yellow
        return "#34d399"  # Green

    def _update_balance_display(self) -> None:
        """Update balance label with current bank balance."""
        from clear_budget.domain.value_objects.amount import Amount
        bank_balance = self.view_model.budget_service.get_bank_balance()
        summary = self.view_model.month_summary
        if summary:
            projected = bank_balance.pence + summary.balance.pence
            self.balance_label.setText(f"Balance: {Amount(pence=projected)}")
            color = self._get_balance_color(projected)
            self.balance_label.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {color}; padding: 5px;"
            )

    def _get_payment_method_label(self, payment_method_id: int) -> str:
        """Get payment method display name."""
        if payment_method_id == 1:
            return "Bank"
        card = self.view_model.budget_service.payment_method_repo.get_credit_card_by_id(card_id=payment_method_id)
        return card.name if card else f"Card {payment_method_id}"

    def update_bills_table(self, summary) -> None:
        """Refresh bills and income tables from month summary."""
        if not summary:
            return

        self.income_label.setText(f"Income: {summary.total_income}")
        self.bills_label.setText(f"Bills: {summary.total_bills}")
        self._update_balance_display()

        self.bills_table.setRowCount(0)
        for bill in self._sort_bills(summary.bills):
            row = self.bills_table.rowCount()
            self.bills_table.insertRow(row)
            self.bills_table.setItem(row, 0, QTableWidgetItem(bill.name))
            self.bills_table.setItem(row, 1, QTableWidgetItem(str(bill.amount)))
            self.bills_table.setItem(row, 2, QTableWidgetItem(self._format_category(bill.category)))
            self.bills_table.setItem(row, 3, QTableWidgetItem(self._get_payment_method_label(bill.payment_method_id)))
            self.bills_table.setItem(row, 4, QTableWidgetItem(str(bill.day_of_month or "N/A")))
            self.bills_table.setItem(row, 5, QTableWidgetItem("✓" if bill.active else "✗"))

        self.income_table.setRowCount(0)
        for income in self._sort_income(summary.income_sources):
            row = self.income_table.rowCount()
            self.income_table.insertRow(row)
            self.income_table.setItem(row, 0, QTableWidgetItem(income.name))
            self.income_table.setItem(row, 1, QTableWidgetItem(str(income.amount)))
            self.income_table.setItem(row, 2, QTableWidgetItem("✓" if income.is_reliable else "✗"))
            self.income_table.setItem(row, 3, QTableWidgetItem("✓" if income.active else "✗"))


    def on_edit_balance(self) -> None:
        """Handle edit balance button click."""
        current_balance = self.view_model.budget_service.get_bank_balance()
        dialog = BalanceDialog(self, current_balance)
        if dialog.exec() == BalanceDialog.Accepted:
            balance = dialog.get_balance()
            if balance is not None:
                self.view_model.budget_service.set_bank_balance(amount=balance)
                summary = self.view_model.budget_service.get_month_summary(
                    year_month=self.view_model.current_month
                )
                self.view_model.month_summary = summary
                self._update_balance_display()

    def on_add_bill(self) -> None:
        """Handle add bill button click."""
        dialog = BillDialog(
            self,
            None,
            payment_method_repo=self.view_model.budget_service.payment_method_repo,
            current_month=self.view_model.current_month,
        )
        if dialog.exec() == BillDialog.Accepted:
            bill = dialog.get_bill()
            if bill:
                self.view_model.add_bill(bill=bill)

    def _get_bill_from_row(self, row: int):
        """Get bill from table row by name lookup."""
        if row < 0 or not self.view_model.month_summary:
            return None
        bill_name = self.bills_table.item(row, 0).text()
        return next((b for b in self.view_model.month_summary.bills if b.name == bill_name), None)

    def on_edit_bill(self) -> None:
        """Handle edit bill button click."""
        bill = self._get_bill_from_row(self.bills_table.currentRow())
        if not bill:
            return
        dialog = BillDialog(
            self,
            bill,
            payment_method_repo=self.view_model.budget_service.payment_method_repo,
            current_month=self.view_model.current_month,
        )
        if dialog.exec() == BillDialog.Accepted:
            edited_bill = dialog.get_bill()
            if edited_bill:
                self.view_model.update_bill(bill=edited_bill)

    def on_delete_bill(self) -> None:
        """Handle delete bill button click."""
        bill = self._get_bill_from_row(self.bills_table.currentRow())
        if bill:
            self.view_model.delete_bill(bill_id=bill.id)

    def on_add_income(self) -> None:
        """Handle add income button click."""
        dialog = IncomeDialog(self, None)
        if dialog.exec() == IncomeDialog.Accepted:
            income = dialog.get_income()
            if income:
                self.view_model.add_income(income=income)

    def on_edit_income(self) -> None:
        """Handle edit income button click."""
        row = self.income_table.currentRow()
        if row < 0 or not self.view_model.month_summary:
            return
        income_sources = list(self.view_model.month_summary.income_sources)
        if row >= len(income_sources):
            return
        income = income_sources[row]
        dialog = IncomeDialog(self, income)
        if dialog.exec() == IncomeDialog.Accepted:
            edited_income = dialog.get_income()
            if edited_income:
                self.view_model.update_income(income=edited_income)

    def on_delete_income(self) -> None:
        """Handle delete income button click."""
        row = self.income_table.currentRow()
        if row < 0 or not self.view_model.month_summary:
            return
        income_sources = list(self.view_model.month_summary.income_sources)
        if row >= len(income_sources):
            return
        self.view_model.delete_income(income_id=income_sources[row].id)
