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
from PySide6.QtCore import Qt

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.widgets.bill_dialog import BillDialog
from clear_budget.ui.widgets.income_dialog import IncomeDialog
from clear_budget.ui.widgets.balance_dialog import BalanceDialog
from clear_budget.ui.widgets.clickable_label import ClickableLabel
from clear_budget.ui.utils.format_helpers import MONTH_NAMES, format_category


_BANK_ACCOUNT_ID = 1
_BILLS_SORT_KEYS = {
    0: lambda b: b.name.lower(),
    1: lambda b: b.amount.pence,
    2: lambda b: b.category.lower(),
    3: lambda b: b.payment_method_id,
    4: lambda b: b.day_of_month or 99,
    5: lambda b: not b.active,
}
_INCOME_SORT_KEYS = {
    0: lambda i: i.name.lower(),
    1: lambda i: i.amount.pence,
    2: lambda i: not i.is_reliable,
    3: lambda i: i.day_of_month or 99,
    4: lambda i: not i.active,
}


class MonthView(QWidget):
    """Displays bills and income for current month in tabular form."""

    def __init__(self, view_model: MonthViewModel) -> None:
        """Initialize month view widget."""
        super().__init__()
        self.view_model = view_model
        self.add_bill_btn = None
        self.delete_bill_btn = None
        self.add_income_btn = None
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
        prev_btn, next_btn = self._build_header_section(layout)
        self._build_bills_section(layout)
        self._build_income_section(layout)
        self.setLayout(layout)
        self._connect_button_signals(prev_btn, next_btn)

    def _build_header_section(self, layout: QVBoxLayout) -> tuple:
        """Build header section with navigation, month label, and summary."""
        header_layout = QVBoxLayout()

        nav_layout = QHBoxLayout()
        prev_btn = QPushButton("← Previous")
        next_btn = QPushButton("Next →")
        self.archive_btn = QPushButton("Archive Month")
        nav_layout.addWidget(prev_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.archive_btn)
        nav_layout.addWidget(next_btn)
        header_layout.addLayout(nav_layout)

        month_str = f"{MONTH_NAMES[self.view_model.current_month.month]} {self.view_model.current_month.year}"
        self.month_label = QLabel(month_str)
        self.month_label.setStyleSheet(
            "font-size: 36px; font-weight: bold; padding: 20px; "
            "background-color: #1a1a2e; color: #00d4ff; text-align: center; border-radius: 8px;"
        )
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.month_label)

        summary_layout = QHBoxLayout()
        self.income_label = QLabel("Income: £0.00")
        self.income_label.setStyleSheet("font-size: 14px; padding: 5px;")
        self.bills_label = QLabel("Bills: £0.00")
        self.bills_label.setStyleSheet("font-size: 14px; padding: 5px;")

        self.edit_balance_btn = QPushButton("📝")
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
        return prev_btn, next_btn

    def _build_bills_section(self, layout: QVBoxLayout) -> None:
        """Build bills table section."""
        bills_group = QGroupBox("Bills")
        bills_layout = QVBoxLayout()

        self.bills_table = QTableWidget()
        self.bills_table.setColumnCount(6)
        self.bills_table.setHorizontalHeaderLabels(
            ["Name", "Amount", "Category", "Payment Method", "Due", "Active"]
        )
        self.bills_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bills_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.bills_table.setColumnWidth(0, 120)
        self.bills_table.setColumnWidth(1, 100)
        self.bills_table.setColumnWidth(2, 130)
        self.bills_table.setColumnWidth(3, 140)
        self.bills_table.setColumnWidth(4, 80)
        self.bills_table.setColumnWidth(5, 70)
        self.bills_table.verticalHeader().setStyleSheet("QHeaderView::section { color: #34d399; }")
        self.bills_table.verticalHeader().sectionClicked.connect(self._on_bill_row_header_click)
        self.bills_table.horizontalHeader().sectionClicked.connect(self.on_bills_header_click)
        bills_layout.addWidget(self.bills_table)

        bills_btn_layout = QHBoxLayout()
        self.add_bill_btn = QPushButton("Add Bill")
        self.delete_bill_btn = QPushButton("Delete Bill")
        bills_btn_layout.addWidget(self.add_bill_btn)
        bills_btn_layout.addStretch()
        bills_btn_layout.addWidget(self.delete_bill_btn)
        bills_layout.addLayout(bills_btn_layout)

        bills_group.setLayout(bills_layout)
        layout.addWidget(bills_group)

    def _build_income_section(self, layout: QVBoxLayout) -> None:
        """Build income table section."""
        income_group = QGroupBox("Income")
        income_layout = QVBoxLayout()

        self.income_table = QTableWidget()
        self.income_table.setColumnCount(5)
        self.income_table.setHorizontalHeaderLabels(
            ["Name", "Amount", "Reliable", "Due Day", "Active"]
        )
        self.income_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.income_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.income_table.verticalHeader().setStyleSheet("QHeaderView::section { color: #34d399; }")
        self.income_table.verticalHeader().sectionClicked.connect(self._on_income_row_header_click)
        self.income_table.horizontalHeader().sectionClicked.connect(self.on_income_header_click)
        income_layout.addWidget(self.income_table)

        income_btn_layout = QHBoxLayout()
        self.add_income_btn = QPushButton("Add Income")
        self.delete_income_btn = QPushButton("Delete Income")
        income_btn_layout.addWidget(self.add_income_btn)
        income_btn_layout.addStretch()
        income_btn_layout.addWidget(self.delete_income_btn)
        income_layout.addLayout(income_btn_layout)

        income_group.setLayout(income_layout)
        layout.addWidget(income_group)

    def _connect_button_signals(self, prev_btn: QPushButton, next_btn: QPushButton) -> None:
        """Connect button signals to handlers."""
        prev_btn.clicked.connect(self.view_model.previous_month)
        next_btn.clicked.connect(self.view_model.next_month)
        self.archive_btn.clicked.connect(self.on_archive_month)
        self.edit_balance_btn.clicked.connect(self.on_edit_balance)
        self.add_bill_btn.clicked.connect(self.on_add_bill)
        self.delete_bill_btn.clicked.connect(self.on_delete_bill)
        self.add_income_btn.clicked.connect(self.on_add_income)
        self.delete_income_btn.clicked.connect(self.on_delete_income)

    def connect_signals(self) -> None:
        """Connect ViewModel signals to view updates."""
        self.view_model.month_summary_updated.connect(self.update_bills_table)
        self.view_model.month_changed.connect(self._update_month_label)

    def _update_month_label(self, year_month) -> None:
        """Update month label when month changes."""
        month_str = f"{MONTH_NAMES[year_month.month]} {year_month.year}"
        self.month_label.setText(month_str)
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _toggle_sort(self, current_col: int, current_asc: bool, new_col: int) -> tuple:
        """Toggle sort column/direction. Returns (new_col, new_asc)."""
        return (new_col, not current_asc) if current_col == new_col else (new_col, True)

    def on_bills_header_click(self, logical_index: int) -> None:
        """Handle bill table header click for sorting."""
        self.bills_sort_column, self.bills_sort_ascending = self._toggle_sort(
            self.bills_sort_column, self.bills_sort_ascending, logical_index
        )
        self.view_model.refresh_month_summary()

    def on_income_header_click(self, logical_index: int) -> None:
        """Handle income table header click for sorting."""
        self.income_sort_column, self.income_sort_ascending = self._toggle_sort(
            self.income_sort_column, self.income_sort_ascending, logical_index
        )
        self.view_model.refresh_month_summary()

    def _sort_bills(self, bills) -> list:
        """Sort bills based on current sort settings."""
        key_fn = _BILLS_SORT_KEYS.get(self.bills_sort_column, lambda b: b.name.lower())
        return sorted(bills, key=key_fn, reverse=not self.bills_sort_ascending)

    def _sort_income(self, income_sources) -> list:
        """Sort income sources based on current sort settings."""
        key_fn = _INCOME_SORT_KEYS.get(self.income_sort_column, lambda i: i.name.lower())
        return sorted(income_sources, key=key_fn, reverse=not self.income_sort_ascending)

    def _get_balance_color(self, balance_pence: int) -> str:
        """Get color for balance display."""
        if balance_pence < 0:
            return "#f87171"
        return "#fbbf24" if balance_pence < 10000 else "#34d399"

    def _update_balance_display(self) -> None:
        """Update balance label with current bank balance."""
        bank_balance = self.view_model.budget_service.get_bank_balance()
        summary = self.view_model.month_summary
        if summary:
            projected = bank_balance.pence + summary.balance.pence
            self.balance_label.setText(f"Balance: {Amount(pence=projected)}")
            color = self._get_balance_color(projected)
            self.balance_label.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {color}; padding: 5px;"
            )

    def _get_payment_method_label(self, payment_method_id: int, card_map: dict[int, str]) -> str:
        """Get payment method display name."""
        if payment_method_id == _BANK_ACCOUNT_ID:
            return "Bank"
        return card_map.get(payment_method_id, f"Card {payment_method_id}")

    def update_bills_table(self, summary) -> None:
        """Refresh bills and income tables from month summary."""
        if not summary:
            return

        self.income_label.setText(f"Income: {summary.total_income}")
        self.bills_label.setText(f"Bills: {summary.total_bills}")
        self._update_balance_display()

        # Pre-fetch card map for efficient label lookup
        cards = self.view_model.budget_service.payment_method_repo.get_all_credit_cards()
        card_map = {c.id: c.name for c in cards}

        self.bills_table.setRowCount(0)
        for row, bill in enumerate(self._sort_bills(summary.bills)):
            self.bills_table.insertRow(row)
            self.bills_table.setVerticalHeaderItem(row, QTableWidgetItem("📝"))
            self.bills_table.setItem(row, 0, QTableWidgetItem(bill.name))
            self.bills_table.setItem(row, 1, QTableWidgetItem(str(bill.amount)))
            self.bills_table.setItem(row, 2, QTableWidgetItem(format_category(bill.category)))
            self.bills_table.setItem(row, 3, QTableWidgetItem(self._get_payment_method_label(bill.payment_method_id, card_map)))
            self.bills_table.setItem(row, 4, QTableWidgetItem(str(bill.day_of_month or "N/A")))
            self.bills_table.setItem(row, 5, QTableWidgetItem("✓" if bill.active else "✗"))

        self.income_table.setRowCount(0)
        for row, income in enumerate(self._sort_income(summary.income_sources)):
            self.income_table.insertRow(row)
            self.income_table.setVerticalHeaderItem(row, QTableWidgetItem("📝"))
            self.income_table.setItem(row, 0, QTableWidgetItem(income.name))
            self.income_table.setItem(row, 1, QTableWidgetItem(str(income.amount)))
            self.income_table.setItem(row, 2, QTableWidgetItem("✓" if income.is_reliable else "✗"))
            self.income_table.setItem(row, 3, QTableWidgetItem(str(income.day_of_month) if income.day_of_month else "~"))
            self.income_table.setItem(row, 4, QTableWidgetItem("✓" if income.active else "✗"))


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

    def on_archive_month(self) -> None:
        """Archive the current month."""
        self.view_model.budget_service.archive_month(year_month=self.view_model.current_month)

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

    def _get_income_from_row(self, row: int):
        """Get income from table row (sorted list index)."""
        if row < 0 or not self.view_model.month_summary:
            return None
        income_sources = list(self._sort_income(self.view_model.month_summary.income_sources))
        if row >= len(income_sources):
            return None
        return income_sources[row]

    def _on_bill_row_header_click(self, row: int) -> None:
        """Handle pencil icon click on bill row header."""
        bill = self._get_bill_from_row(row)
        if bill:
            self._edit_bill_dialog(bill)

    def _edit_bill_dialog(self, bill) -> None:
        """Show edit dialog for a bill."""
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

    def _on_income_row_header_click(self, row: int) -> None:
        """Handle pencil icon click on income row header."""
        income = self._get_income_from_row(row)
        if income:
            self._edit_income_dialog(income)

    def _edit_income_dialog(self, income) -> None:
        """Show edit dialog for income."""
        dialog = IncomeDialog(self, income)
        if dialog.exec() == IncomeDialog.Accepted:
            edited_income = dialog.get_income()
            if edited_income:
                self.view_model.update_income(income=edited_income)

    def on_delete_income(self) -> None:
        """Handle delete income button click."""
        income = self._get_income_from_row(self.income_table.currentRow())
        if income:
            self.view_model.delete_income(income_id=income.id)
