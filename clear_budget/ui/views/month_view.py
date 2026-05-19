"""Month budget view widget - displays bills and income for selected month."""

import dataclasses

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QGroupBox,
    QHeaderView,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

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
_EDITABLE = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

def _ei(text: str) -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setFlags(_EDITABLE)
    return it

class MonthView(QWidget):
    """Displays bills and income for current month in tabular form."""

    def __init__(self, view_model: MonthViewModel) -> None:
        super().__init__()
        self.view_model = view_model
        self.add_bill_btn = self.delete_bill_btn = None
        self.add_income_btn = self.delete_income_btn = None
        self.month_label = self.prev_btn = None
        self.bills_sort_column = 4
        self.bills_sort_ascending = True
        self.income_sort_column = 0
        self.income_sort_ascending = True
        self.init_ui()
        self.connect_signals()
        self.view_model.refresh_month_summary()

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        prev_btn, next_btn = self._build_header_section(layout)
        self._build_bills_section(layout)
        self._build_income_section(layout)
        self.setLayout(layout)
        self._connect_button_signals(prev_btn, next_btn)

    def _build_header_section(self, layout: QVBoxLayout) -> tuple:
        header_layout = QVBoxLayout()
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("← Previous")
        next_btn = QPushButton("Next →")
        self.archive_btn = QPushButton("Archive Month")
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.archive_btn)
        nav_layout.addWidget(next_btn)
        header_layout.addLayout(nav_layout)

        self.month_label = QLabel(f"{MONTH_NAMES[self.view_model.current_month.month]} {self.view_model.current_month.year}")
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
        self.balance_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #34d399; padding: 5px;")
        summary_layout.addWidget(self.income_label)
        summary_layout.addWidget(self.bills_label)
        summary_layout.addStretch()
        summary_layout.addWidget(self.edit_balance_btn)
        summary_layout.addWidget(self.balance_label)
        header_layout.addLayout(summary_layout)
        layout.addLayout(header_layout)
        return self.prev_btn, next_btn

    def _build_bills_section(self, layout: QVBoxLayout) -> None:
        bills_group = QGroupBox("Bills")
        bills_layout = QVBoxLayout()
        self.bills_table = QTableWidget()
        self.bills_table.setColumnCount(6)
        self.bills_table.setHorizontalHeaderLabels(
            ["Name", "Amount", "Category", "Payment Method", "Due", "Active"]
        )
        self.bills_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bills_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.bills_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self.bills_table.setStyleSheet(
            "QTableWidget::indicator{width:15px;height:15px;border:2px solid #9ca3af;"
            "border-radius:3px;background:transparent;}"
            "QTableWidget::indicator:checked{background:#34d399;border-color:#34d399;}"
            "QTableWidget::indicator:unchecked:hover{border-color:#d1d5db;}"
        )
        _bh = self.bills_table.horizontalHeader()
        _bh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        _bh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        _bh.setStretchLastSection(False)
        self.bills_table.verticalHeader().setStyleSheet("QHeaderView::section { color: #34d399; }")
        self.bills_table.verticalHeader().sectionClicked.connect(self._on_bill_row_header_click)
        self.bills_table.horizontalHeader().sectionClicked.connect(self.on_bills_header_click)
        bills_layout.addWidget(self.bills_table)
        bills_btn_layout = QHBoxLayout()
        self.add_bill_btn = QPushButton("Add Bill")
        self.delete_bill_btn = QPushButton("Delete Bill")
        self.delete_bill_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        bills_btn_layout.addWidget(self.add_bill_btn)
        bills_btn_layout.addStretch()
        bills_btn_layout.addWidget(self.delete_bill_btn)
        bills_layout.addLayout(bills_btn_layout)
        bills_group.setLayout(bills_layout)
        layout.addWidget(bills_group)

    def _build_income_section(self, layout: QVBoxLayout) -> None:
        income_group = QGroupBox("Income")
        income_layout = QVBoxLayout()
        self.income_table = QTableWidget()
        self.income_table.setColumnCount(5)
        self.income_table.setHorizontalHeaderLabels(
            ["Name", "Amount", "Reliable", "Due Day", "Active"]
        )
        self.income_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.income_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.income_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        _ih = self.income_table.horizontalHeader()
        _ih.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        _ih.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        _ih.setStretchLastSection(False)
        self.income_table.setStyleSheet(
            "QTableWidget::indicator{width:15px;height:15px;border:2px solid #9ca3af;"
            "border-radius:3px;background:transparent;}"
            "QTableWidget::indicator:checked{background:#34d399;border-color:#34d399;}"
            "QTableWidget::indicator:unchecked:hover{border-color:#d1d5db;}"
        )
        self.income_table.verticalHeader().setStyleSheet("QHeaderView::section { color: #34d399; }")
        self.income_table.verticalHeader().sectionClicked.connect(self._on_income_row_header_click)
        self.income_table.horizontalHeader().sectionClicked.connect(self.on_income_header_click)
        income_layout.addWidget(self.income_table)
        income_btn_layout = QHBoxLayout()
        self.add_income_btn = QPushButton("Add Income")
        self.delete_income_btn = QPushButton("Delete Income")
        self.delete_income_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        income_btn_layout.addWidget(self.add_income_btn)
        income_btn_layout.addStretch()
        income_btn_layout.addWidget(self.delete_income_btn)
        income_layout.addLayout(income_btn_layout)
        income_group.setLayout(income_layout)
        layout.addWidget(income_group)

    def _connect_button_signals(self, prev_btn: QPushButton, next_btn: QPushButton) -> None:
        prev_btn.clicked.connect(self.view_model.previous_month)
        next_btn.clicked.connect(self.view_model.next_month)
        self.archive_btn.clicked.connect(self.on_archive_month)
        self.edit_balance_btn.clicked.connect(self.on_edit_balance)
        self.add_bill_btn.clicked.connect(self.on_add_bill)
        self.delete_bill_btn.clicked.connect(self.on_delete_bill)
        self.add_income_btn.clicked.connect(self.on_add_income)
        self.delete_income_btn.clicked.connect(self.on_delete_income)

    def connect_signals(self) -> None:
        self.view_model.month_summary_updated.connect(self.update_bills_table)
        self.view_model.month_changed.connect(self._update_month_label)
        self.view_model.month_changed.connect(self._update_prev_btn_state)
        self.bills_table.cellClicked.connect(self._on_bill_cell_clicked)
        self.bills_table.itemChanged.connect(self._on_bill_item_changed)
        self.income_table.cellClicked.connect(self._on_income_cell_clicked)
        self.income_table.itemChanged.connect(self._on_income_item_changed)
        self._update_prev_btn_state(self.view_model.current_month)

    def _update_prev_btn_state(self, year_month) -> None:
        if self.prev_btn:
            self.prev_btn.setEnabled(year_month > self.view_model.base_month)

    def _update_month_label(self, year_month) -> None:
        self.month_label.setText(f"{MONTH_NAMES[year_month.month]} {year_month.year}")
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _toggle_sort(self, current_col: int, current_asc: bool, new_col: int) -> tuple:
        return (new_col, not current_asc) if current_col == new_col else (new_col, True)

    def on_bills_header_click(self, i: int) -> None:
        self.bills_sort_column, self.bills_sort_ascending = self._toggle_sort(self.bills_sort_column, self.bills_sort_ascending, i)
        self.view_model.refresh_month_summary()

    def on_income_header_click(self, i: int) -> None:
        self.income_sort_column, self.income_sort_ascending = self._toggle_sort(self.income_sort_column, self.income_sort_ascending, i)
        self.view_model.refresh_month_summary()

    def _sort_bills(self, bills) -> list:
        return sorted(bills, key=_BILLS_SORT_KEYS.get(self.bills_sort_column, lambda b: b.name.lower()), reverse=not self.bills_sort_ascending)

    def _sort_income(self, income_sources) -> list:
        return sorted(income_sources, key=_INCOME_SORT_KEYS.get(self.income_sort_column, lambda i: i.name.lower()), reverse=not self.income_sort_ascending)

    def _get_balance_color(self, p: int) -> str:
        return "#f87171" if p < 0 else "#fbbf24" if p < 10000 else "#34d399"

    def _update_balance_display(self) -> None:
        bank = self.view_model.budget_service.get_bank_balance()
        if summary := self.view_model.month_summary:
            projected = bank.pence + summary.balance.pence
            self.balance_label.setText(f"Balance: {Amount(pence=projected)}")
            self.balance_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {self._get_balance_color(projected)}; padding: 5px;")

    def _get_payment_method_label(self, mid: int, card_map: dict) -> str:
        return "Bank" if mid == _BANK_ACCOUNT_ID else card_map.get(mid, f"Card {mid}")

    def _on_bill_cell_clicked(self, row: int, col: int) -> None:
        if col != 5: return
        from PySide6.QtWidgets import QApplication
        mods = QApplication.keyboardModifiers()
        bill = self._get_bill_from_row(row)
        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            item = self.bills_table.item(row, 5)
            if item and bill:
                self.bills_table.blockSignals(True)
                item.setCheckState(Qt.CheckState.Checked if bill.active else Qt.CheckState.Unchecked)
                self.bills_table.blockSignals(False)
            return
        if bill is not None: self.view_model.set_bill_active(bill_id=bill.id, active=not bill.active)

    _EDITABLE_BILL_COLS = {0, 1, 2, 4}

    def _on_bill_item_changed(self, item) -> None:
        if item.column() not in self._EDITABLE_BILL_COLS:
            QTimer.singleShot(0, self.view_model.refresh_month_summary)
            return
        bill = self._get_bill_from_row(item.row())
        if bill is None: return
        col, v = item.column(), item.text().strip()
        try:
            if col == 0: u = dataclasses.replace(bill, name=v or bill.name)
            elif col == 1: u = dataclasses.replace(bill, amount=Amount.from_pounds(float(v.lstrip('£'))))
            elif col == 2: u = dataclasses.replace(bill, category=v.lower().replace(' ', '_'))
            elif col == 4: u = dataclasses.replace(bill, day_of_month=int(v))
            else: return
            if u == bill: return
            QTimer.singleShot(0, lambda: self.view_model.update_bill(bill=u))
        except (ValueError, AttributeError): QTimer.singleShot(0, self.view_model.refresh_month_summary)

    _EDITABLE_INCOME_COLS = {0, 1, 3}

    def _on_income_item_changed(self, item) -> None:
        if item.column() in (2, 4):
            return
        if item.column() not in self._EDITABLE_INCOME_COLS:
            QTimer.singleShot(0, self.view_model.refresh_month_summary)
            return
        inc = self._get_income_from_row(item.row())
        if inc is None: return
        col, v = item.column(), item.text().strip()
        try:
            if col == 0: u = dataclasses.replace(inc, name=v or inc.name)
            elif col == 1: u = dataclasses.replace(inc, amount=Amount.from_pounds(float(v.lstrip('£'))))
            elif col == 3: u = dataclasses.replace(inc, day_of_month=int(v) if v.isdigit() else None)
            else: return
            if u == inc: return
            QTimer.singleShot(0, lambda: self.view_model.update_income(income=u))
        except (ValueError, AttributeError): QTimer.singleShot(0, self.view_model.refresh_month_summary)

    def _on_income_cell_clicked(self, row: int, col: int) -> None:
        if col not in (2, 4): return
        from PySide6.QtWidgets import QApplication
        mods = QApplication.keyboardModifiers()
        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            return
        inc = self._get_income_from_row(row)
        if inc is None: return
        if col == 2:
            QTimer.singleShot(0, lambda: self.view_model.update_income(income=dataclasses.replace(inc, is_reliable=not inc.is_reliable)))
        else:
            QTimer.singleShot(0, lambda: self.view_model.update_income(income=dataclasses.replace(inc, active=not inc.active)))

    def update_bills_table(self, summary) -> None:
        if not summary: return
        self.income_label.setText(f"Income: {summary.total_income}")
        self.bills_label.setText(f"Bills: {summary.total_bills}")
        self._update_balance_display()
        cards = self.view_model.budget_service.payment_method_repo.get_all_credit_cards()
        card_map = {c.id: c.name for c in cards}
        self.bills_table.blockSignals(True); self.bills_table.setRowCount(0); self.bills_table.blockSignals(False)
        self.bills_table.blockSignals(True)
        for row, bill in enumerate(self._sort_bills(summary.all_bills)):
            self.bills_table.insertRow(row)
            self.bills_table.setVerticalHeaderItem(row, QTableWidgetItem("📝"))
            name_item = _ei(bill.name)
            name_item.setData(Qt.ItemDataRole.UserRole, bill.id)
            self.bills_table.setItem(row, 0, name_item)
            self.bills_table.setItem(row, 1, _ei(str(bill.amount)))
            self.bills_table.setItem(row, 2, _ei(format_category(bill.category)))
            self.bills_table.setItem(row, 3, QTableWidgetItem(self._get_payment_method_label(bill.payment_method_id, card_map)))
            self.bills_table.setItem(row, 4, _ei(str(bill.day_of_month or "N/A")))
            active_item = QTableWidgetItem()
            active_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
            active_item.setCheckState(Qt.CheckState.Checked if bill.active else Qt.CheckState.Unchecked)
            self.bills_table.setItem(row, 5, active_item)
            if self.view_model.current_month == self.view_model.base_month and bill.day_of_month:
                d, t = bill.day_of_month, self.view_model.today.day
                color = QColor("#9ca3af") if d < t else QColor("#fbbf24") if d == t else None
                if color:
                    for c in range(self.bills_table.columnCount()):
                        it = self.bills_table.item(row, c)
                        if it:
                            it.setForeground(color)
        self.bills_table.blockSignals(False)
        self.income_table.blockSignals(True); self.income_table.setRowCount(0); self.income_table.blockSignals(False)
        self.income_table.blockSignals(True)
        for row, income in enumerate(self._sort_income(summary.all_income_sources)):
            self.income_table.insertRow(row)
            self.income_table.setVerticalHeaderItem(row, QTableWidgetItem("📝"))
            name_item = _ei(income.name)
            name_item.setData(Qt.ItemDataRole.UserRole, income.id)
            self.income_table.setItem(row, 0, name_item)
            self.income_table.setItem(row, 1, _ei(str(income.amount)))
            reliable_item = QTableWidgetItem()
            reliable_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
            reliable_item.setCheckState(Qt.CheckState.Checked if income.is_reliable else Qt.CheckState.Unchecked)
            self.income_table.setItem(row, 2, reliable_item)
            self.income_table.setItem(row, 3, _ei(str(income.day_of_month) if income.day_of_month else "~"))
            active_item = QTableWidgetItem()
            active_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
            active_item.setCheckState(Qt.CheckState.Checked if income.active else Qt.CheckState.Unchecked)
            self.income_table.setItem(row, 4, active_item)
        self.income_table.blockSignals(False)

    def on_edit_balance(self) -> None:
        dialog = BalanceDialog(self, self.view_model.budget_service.get_bank_balance())
        if dialog.exec() == BalanceDialog.Accepted and (balance := dialog.get_balance()) is not None:
            self.view_model.budget_service.set_bank_balance(amount=balance)
            self.view_model.month_summary = self.view_model.budget_service.get_month_summary(year_month=self.view_model.current_month)
            self._update_balance_display()

    def on_archive_month(self) -> None:
        self.view_model.budget_service.archive_month(year_month=self.view_model.current_month)

    def on_add_bill(self) -> None:
        dialog = BillDialog(
            self, None,
            payment_method_repo=self.view_model.budget_service.payment_method_repo,
            current_month=self.view_model.current_month,
        )
        if dialog.exec() == BillDialog.Accepted and (bill := dialog.get_bill()):
            self.view_model.add_bill(bill=bill)

    def _get_bill_from_row(self, row: int):
        if row < 0 or not self.view_model.month_summary: return None
        item = self.bills_table.item(row, 0)
        if item is None: return None
        bill_id = item.data(Qt.ItemDataRole.UserRole)
        return next((b for b in self.view_model.month_summary.all_bills if b.id == bill_id), None)

    def _get_income_from_row(self, row: int):
        if row < 0 or not self.view_model.month_summary: return None
        item = self.income_table.item(row, 0)
        if item is None: return None
        iid = item.data(Qt.ItemDataRole.UserRole)
        return next((i for i in self.view_model.month_summary.all_income_sources if i.id == iid), None)

    def _on_bill_row_header_click(self, row: int) -> None:
        if bill := self._get_bill_from_row(row): self._edit_bill_dialog(bill)

    def _edit_bill_dialog(self, bill) -> None:
        dialog = BillDialog(
            self, bill,
            payment_method_repo=self.view_model.budget_service.payment_method_repo,
            current_month=self.view_model.current_month,
        )
        if dialog.exec() == BillDialog.Accepted and (eb := dialog.get_bill()):
            fn = self.view_model.update_bill_for_month if dialog.month_only_check.isChecked() else self.view_model.update_bill
            fn(bill=eb)

    def on_delete_bill(self) -> None:
        rows = sorted({idx.row() for idx in self.bills_table.selectedIndexes()})
        ids = [b.id for r in rows if (b := self._get_bill_from_row(r)) is not None]
        if ids: self.view_model.delete_bills(bill_ids=ids)

    def on_add_income(self) -> None:
        dialog = IncomeDialog(self, None)
        if dialog.exec() == IncomeDialog.Accepted and (inc := dialog.get_income()):
            self.view_model.add_income(income=inc)

    def _on_income_row_header_click(self, row: int) -> None:
        if inc := self._get_income_from_row(row): self._edit_income_dialog(inc)

    def _edit_income_dialog(self, income) -> None:
        dialog = IncomeDialog(self, income)
        if dialog.exec() == IncomeDialog.Accepted and (inc := dialog.get_income()):
            self.view_model.update_income(income=inc)

    def on_delete_income(self) -> None:
        rows = sorted({idx.row() for idx in self.income_table.selectedIndexes()})
        ids = [i.id for r in rows if (i := self._get_income_from_row(r)) is not None]
        if ids: self.view_model.delete_incomes(income_ids=ids)
