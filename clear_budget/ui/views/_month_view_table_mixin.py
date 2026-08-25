"""MonthViewTableMixin - table population extracted from MonthView (LOC limit).

The bills table also carries a REMINDER row for each commitment whose money
leaves during the viewed month. It is not a bill and must never behave like
one: it is inert to every edit path, it adds nothing to the total and it says
in its own name where it came from. It exists so the same obligation is not
entered twice, which would take the money once as a bill and again as a
reserve.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidgetItem

from clear_budget.ui import theme
from clear_budget.ui.utils import reserves_text
from clear_budget.ui.utils.format_helpers import format_category

_BANK_ACCOUNT_ID = 1
_EDITABLE = (
    Qt.ItemFlag.ItemIsEnabled
    | Qt.ItemFlag.ItemIsSelectable
    | Qt.ItemFlag.ItemIsEditable
)
# A reminder row can be read and nothing else: not edited, not ticked. The
# flags are the first of two guards; `_get_bill_from_row` is the second, so a
# path that never touches these flags still cannot mistake one for a bill.
_READ_ONLY = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

# Marks a row as a commitment reminder rather than a bill. Read by
# `_get_bill_from_row`, which is where every edit and delete path starts.
COMMITMENT_ROLE = Qt.ItemDataRole.UserRole + 1


def _ei(text: str) -> QTableWidgetItem:
    """Return an editable QTableWidgetItem."""
    item = QTableWidgetItem(text)
    item.setFlags(_EDITABLE)
    return item


def _ro(text: str) -> QTableWidgetItem:
    """Return a read-only QTableWidgetItem, for a row that is not a bill."""
    item = QTableWidgetItem(text)
    item.setFlags(_READ_ONLY)
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
        bills = self._sort_bills(summary.all_bills)
        for row, bill in enumerate(bills):
            self._add_bill_row(row, bill, card_map)
        # After the bills rather than sorted among them: a reminder that reads
        # as one of the rows around it is the confusion this exists to stop.
        for offset, due in enumerate(self._commitments_due()):
            self._add_commitment_row(len(bills) + offset, due)
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
        name_item = _ei(bill.name)
        name_item.setData(Qt.ItemDataRole.UserRole, bill.id)
        self.bills_table.setItem(row, 0, name_item)
        self.bills_table.setItem(row, 1, _ei(str(bill.amount)))
        self.bills_table.setItem(row, 2, _ei(format_category(bill.category)))
        pm_label = self._get_payment_method_label(bill.payment_method_id, card_map)
        self.bills_table.setItem(row, 3, QTableWidgetItem(pm_label))
        self.bills_table.setItem(row, 4, _ei(str(bill.day_of_month or "N/A")))
        self.bills_table.setItem(row, 5, _checkbox_item(bill.active))
        self.bills_table.setItem(row, 6, _checkbox_item(bill.skipped_for_month))
        self.bills_table.setItem(row, 7, _checkbox_item(bill.paid_for_month))
        self._apply_bill_row_style(row, bill, name_item)

    def _commitments_due(self) -> list:
        """The commitments whose money leaves during the viewed month."""
        return self.view_model.budget_service.get_commitments_due_in(
            year_month=self.view_model.current_month
        )

    def _add_commitment_row(self, row: int, due) -> None:
        """One reminder row: read-only throughout, marked as not a bill.

        Every cell is read-only, including the three the bills carry as
        checkboxes: a tick here would say the commitment had been paid or
        skipped, which is a claim only the Reserves page can make.
        """
        self.bills_table.insertRow(row)
        self.bills_table.setVerticalHeaderItem(row, QTableWidgetItem("🔒"))
        name_item = _ro(reserves_text.month_row_name(name=due.name))
        name_item.setData(COMMITMENT_ROLE, True)
        cells = [
            name_item,
            _ro(str(due.amount)),
            _ro(reserves_text.MONTH_ROW_CATEGORY),
            _ro(self._get_payment_method_label(_BANK_ACCOUNT_ID, {})),
            _ro(str(due.day)),
        ]
        tooltip = reserves_text.month_row_tooltip(name=due.name)
        colour = QColor(theme.colours()["info"])
        for column, item in enumerate(cells):
            item.setForeground(colour)
            item.setToolTip(tooltip)
            self.bills_table.setItem(row, column, item)
        # The remaining columns are the bills' own state ticks. Blank rather
        # than unticked: an empty box would invite a click that means nothing.
        for column in range(len(cells), self.bills_table.columnCount()):
            blank = _ro("")
            blank.setToolTip(tooltip)
            self.bills_table.setItem(row, column, blank)

    def _apply_bill_row_style(self, row: int, bill, name_item) -> None:
        if bill.skipped_for_month:
            skip_color = QColor(theme.colours()["text_disabled"])
            for c in range(self.bills_table.columnCount()):
                it = self.bills_table.item(row, c)
                if it:
                    it.setForeground(skip_color)
            name_item.setText(f"{bill.name} (skipped this month)")
        elif bill.has_month_override:
            name_item.setText(f"{bill.name} (*)")
            name_item.setForeground(QColor(theme.colours()["link"]))
        elif (
            self.view_model.current_month == self.view_model.base_month
            and bill.day_of_month
        ):
            self._apply_day_color(self.bills_table, row, bill.day_of_month)

    def _add_income_row(self, row: int, income) -> None:
        self.income_table.insertRow(row)
        self.income_table.setVerticalHeaderItem(row, QTableWidgetItem("📝"))
        name_item = _ei(income.name)
        name_item.setData(Qt.ItemDataRole.UserRole, income.id)
        name_item.setData(Qt.ItemDataRole.UserRole + 1, income.is_month_only)
        self.income_table.setItem(row, 0, name_item)
        self.income_table.setItem(row, 1, _ei(str(income.amount)))
        self.income_table.setItem(row, 2, _checkbox_item(income.is_reliable))
        self.income_table.setItem(
            row,
            3,
            _ei(str(income.day_of_month) if income.day_of_month else "~"),
        )
        self.income_table.setItem(row, 4, _checkbox_item(income.active))
        self.income_table.setItem(row, 5, _checkbox_item(income.skipped_for_month))
        self.income_table.setItem(row, 6, _checkbox_item(income.received_for_month))
        self._apply_income_row_style(row, income, name_item)

    def _apply_income_row_style(self, row: int, income, name_item) -> None:
        if income.is_month_only:
            name_item.setText(f"{income.name} (one-off)")
            name_item.setForeground(QColor(theme.colours()["link"]))
        elif income.skipped_for_month:
            skip_color = QColor(theme.colours()["text_disabled"])
            for c in range(self.income_table.columnCount()):
                it = self.income_table.item(row, c)
                if it:
                    it.setForeground(skip_color)
            name_item.setText(f"{income.name} (skipped this month)")
        elif income.has_month_override:
            name_item.setText(f"{income.name} (*)")
            name_item.setForeground(QColor(theme.colours()["link"]))
        elif (
            self.view_model.current_month == self.view_model.base_month
            and income.day_of_month
        ):
            self._apply_day_color(self.income_table, row, income.day_of_month)

    def _apply_day_color(self, table, row: int, day_of_month: int) -> None:
        t = self.view_model.today.day
        colours = theme.colours()
        color = (
            QColor(colours["text_muted"])
            if day_of_month < t
            else QColor(colours["warn"]) if day_of_month == t else None
        )
        if color:
            for c in range(table.columnCount()):
                it = table.item(row, c)
                if it:
                    it.setForeground(color)
