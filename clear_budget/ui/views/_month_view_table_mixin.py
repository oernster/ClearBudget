"""MonthViewTableMixin - table population extracted from MonthView (LOC limit)."""

from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from clear_budget.ui.utils.format_helpers import format_category

_BANK_ACCOUNT_ID = 1
_EDITABLE = (
    Qt.ItemFlag.ItemIsEnabled
    | Qt.ItemFlag.ItemIsSelectable
    | Qt.ItemFlag.ItemIsEditable
)
_READ_ONLY = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


def _ei(text: str, read_only: bool = False) -> QTableWidgetItem:
    """Return a QTableWidgetItem, editable unless read_only."""
    item = QTableWidgetItem(text)
    item.setFlags(_READ_ONLY if read_only else _EDITABLE)
    return item


def _checkbox_item(checked: bool) -> QTableWidgetItem:
    item = QTableWidgetItem()
    item.setFlags(
        Qt.ItemFlag.ItemIsEnabled
        | Qt.ItemFlag.ItemIsSelectable
        | Qt.ItemFlag.ItemIsUserCheckable
    )
    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    return item


class MonthViewTableMixin:
    """Mixin that provides update_bills_table for MonthView."""

    def update_bills_table(self, summary) -> None:
        if not summary:
            return
        self.income_label.setText(f"Income: {summary.total_income}")
        self.bills_label.setText(f"Bills: {summary.total_bills}")
        self._update_balance_display()
        cards = (
            self.view_model.budget_service.payment_method_repo.get_all_credit_cards()
        )
        card_map = {c.id: c.name for c in cards}
        self.bills_table.blockSignals(True)
        self.bills_table.setRowCount(0)
        self.bills_table.blockSignals(False)
        self.bills_table.blockSignals(True)
        for row, bill in enumerate(self._sort_bills(summary.all_bills)):
            self._add_bill_row(row, bill, card_map)
        self.bills_table.blockSignals(False)
        self.income_table.blockSignals(True)
        self.income_table.setRowCount(0)
        self.income_table.blockSignals(False)
        self.income_table.blockSignals(True)
        for row, income in enumerate(self._sort_income(summary.all_income_sources)):
            self._add_income_row(row, income)
        self.income_table.blockSignals(False)

    def _add_bill_row(self, row: int, bill, card_map: dict) -> None:
        self.bills_table.insertRow(row)
        self.bills_table.setVerticalHeaderItem(row, QTableWidgetItem("📝"))
        name_item = _ei(bill.name, self.read_only)
        name_item.setData(Qt.ItemDataRole.UserRole, bill.id)
        self.bills_table.setItem(row, 0, name_item)
        self.bills_table.setItem(row, 1, _ei(str(bill.amount), self.read_only))
        self.bills_table.setItem(
            row, 2, _ei(format_category(bill.category), self.read_only)
        )
        pm_label = self._get_payment_method_label(bill.payment_method_id, card_map)
        self.bills_table.setItem(row, 3, QTableWidgetItem(pm_label))
        self.bills_table.setItem(
            row, 4, _ei(str(bill.day_of_month or "N/A"), self.read_only)
        )
        self.bills_table.setItem(row, 5, _checkbox_item(bill.active))
        self.bills_table.setItem(row, 6, _checkbox_item(bill.skipped_for_month))
        self.bills_table.setItem(row, 7, _checkbox_item(bill.paid_for_month))
        self._apply_bill_row_style(row, bill, name_item)

    def _apply_bill_row_style(self, row: int, bill, name_item) -> None:
        if bill.skipped_for_month:
            skip_color = QColor("#6b7280")
            for c in range(self.bills_table.columnCount()):
                it = self.bills_table.item(row, c)
                if it:
                    it.setForeground(skip_color)
            name_item.setText(f"{bill.name} (skipped this month)")
        elif bill.has_month_override:
            name_item.setText(f"{bill.name} (*)")
            name_item.setForeground(QColor("#60a5fa"))
        elif (
            self.view_model.current_month == self.view_model.base_month
            and bill.day_of_month
        ):
            self._apply_day_color(self.bills_table, row, bill.day_of_month)

    def _add_income_row(self, row: int, income) -> None:
        self.income_table.insertRow(row)
        self.income_table.setVerticalHeaderItem(row, QTableWidgetItem("📝"))
        name_item = _ei(income.name, self.read_only)
        name_item.setData(Qt.ItemDataRole.UserRole, income.id)
        self.income_table.setItem(row, 0, name_item)
        self.income_table.setItem(row, 1, _ei(str(income.amount), self.read_only))
        self.income_table.setItem(row, 2, _checkbox_item(income.is_reliable))
        self.income_table.setItem(
            row,
            3,
            _ei(
                str(income.day_of_month) if income.day_of_month else "~",
                self.read_only,
            ),
        )
        self.income_table.setItem(row, 4, _checkbox_item(income.active))
        self.income_table.setItem(row, 5, _checkbox_item(income.skipped_for_month))
        self.income_table.setItem(row, 6, _checkbox_item(income.received_for_month))
        self._apply_income_row_style(row, income, name_item)

    def _apply_income_row_style(self, row: int, income, name_item) -> None:
        if income.is_month_only:
            name_item.setText(f"{income.name} (one-off)")
            name_item.setForeground(QColor("#60a5fa"))
        elif income.skipped_for_month:
            skip_color = QColor("#6b7280")
            for c in range(self.income_table.columnCount()):
                it = self.income_table.item(row, c)
                if it:
                    it.setForeground(skip_color)
            name_item.setText(f"{income.name} (skipped this month)")
        elif income.has_month_override:
            name_item.setText(f"{income.name} (*)")
            name_item.setForeground(QColor("#60a5fa"))
        elif (
            self.view_model.current_month == self.view_model.base_month
            and income.day_of_month
        ):
            self._apply_day_color(self.income_table, row, income.day_of_month)

    def _apply_day_color(self, table, row: int, day_of_month: int) -> None:
        t = self.view_model.today.day
        color = (
            QColor("#9ca3af")
            if day_of_month < t
            else QColor("#fbbf24") if day_of_month == t else None
        )
        if color:
            for c in range(table.columnCount()):
                it = table.item(row, c)
                if it:
                    it.setForeground(color)
