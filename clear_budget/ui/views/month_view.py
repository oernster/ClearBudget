"""Month budget view widget - displays bills and income for selected month."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QMessageBox,
)
from PySide6.QtCore import Qt

from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.widgets.bill_dialog import BillDialog
from clear_budget.ui.widgets.income_dialog import IncomeDialog
from clear_budget.ui.widgets.balance_dialog import BalanceDialog
from clear_budget.ui.utils.format_helpers import MONTH_NAMES, fmt
from clear_budget.ui import ui_scale
from clear_budget.ui.views._month_view_builders import MonthViewBuilderMixin
from clear_budget.ui.views._month_view_edit_mixin import MonthViewEditMixin
from clear_budget.ui.views._month_view_table_mixin import (
    MonthViewTableMixin,
    _BANK_ACCOUNT_ID,
)

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


class MonthView(
    MonthViewBuilderMixin, MonthViewTableMixin, MonthViewEditMixin, QWidget
):
    """Displays bills and income for current month in tabular form."""

    def __init__(self, view_model: MonthViewModel, read_only: bool = False) -> None:
        super().__init__()
        self.view_model = view_model
        self.read_only = read_only
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
        self._apply_read_only_state()

    def connect_signals(self) -> None:
        self.view_model.month_summary_updated.connect(self.update_bills_table)
        self.view_model.month_changed.connect(self._update_month_label)
        self.view_model.month_changed.connect(self._update_prev_btn_state)
        self.view_model.month_changed.connect(self._update_archive_btn_state)
        self.bills_table.cellClicked.connect(self._on_bill_cell_clicked)
        self.bills_table.itemChanged.connect(self._on_bill_item_changed)
        self.income_table.cellClicked.connect(self._on_income_cell_clicked)
        self.income_table.itemChanged.connect(self._on_income_item_changed)
        self._update_prev_btn_state(self.view_model.current_month)
        self._update_archive_btn_state(self.view_model.current_month)

    def _update_prev_btn_state(self, year_month) -> None:
        if self.prev_btn:
            self.prev_btn.setEnabled(year_month > self.view_model.base_month)

    def _update_archive_btn_state(self, year_month) -> None:
        self.archive_btn.setEnabled(
            not self.read_only and year_month < YearMonth.today()
        )

    def _update_month_label(self, year_month) -> None:
        self.month_label.setText(f"{MONTH_NAMES[year_month.month]} {year_month.year}")
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _toggle_sort(self, current_col: int, current_asc: bool, new_col: int) -> tuple:
        return (new_col, not current_asc) if current_col == new_col else (new_col, True)

    def on_bills_header_click(self, i: int) -> None:
        self.bills_sort_column, self.bills_sort_ascending = self._toggle_sort(
            self.bills_sort_column, self.bills_sort_ascending, i
        )
        self.view_model.refresh_month_summary()

    def on_income_header_click(self, i: int) -> None:
        self.income_sort_column, self.income_sort_ascending = self._toggle_sort(
            self.income_sort_column, self.income_sort_ascending, i
        )
        self.view_model.refresh_month_summary()

    def _sort_bills(self, bills) -> list:
        return sorted(
            bills,
            key=_BILLS_SORT_KEYS.get(self.bills_sort_column, lambda b: b.name.lower()),
            reverse=not self.bills_sort_ascending,
        )

    def _sort_income(self, income_sources) -> list:
        return sorted(
            income_sources,
            key=_INCOME_SORT_KEYS.get(
                self.income_sort_column, lambda i: i.name.lower()
            ),
            reverse=not self.income_sort_ascending,
        )

    def _get_balance_color(self, p: int) -> str:
        return "#f87171" if p < 0 else "#fbbf24" if p < 10000 else "#34d399"

    def _update_balance_display(self) -> None:
        if summary := self.view_model.month_summary:
            from clear_budget.domain.value_objects.year_month import YearMonth as _YM
            from datetime import datetime as _dt

            today_ym = _YM(_dt.now().year, _dt.now().month)
            if self.view_model.current_month == today_ym:
                today_day = _dt.now().day
                pence = self.view_model.budget_service.get_bank_balance().pence
                balance_day = self.view_model.budget_service._get_bank_balance_day()
                if balance_day > 0:
                    arrived_pence = sum(
                        i.amount.pence
                        for i in summary.income_sources
                        if i.day_of_month and balance_day < i.day_of_month <= today_day
                    )
                    pence += arrived_pence
                label = f"Balance: {fmt(pence)}"
            else:
                _svc = self.view_model.budget_service
                pence = _svc.get_projected_month_end_balance_pence(
                    year_month=self.view_model.current_month,
                    summary=summary,
                )
                if pence >= 0:
                    label = f"Projected end: {fmt(pence)}"
                else:
                    label = f"Projected end: -{fmt(abs(pence))} OVERDRAWN"
            self.balance_label.setText(label)
            color = self._get_balance_color(pence)
            self.balance_label.setStyleSheet(
                ui_scale.style(
                    f"font-size: 20px; font-weight: bold;"
                    f" color: {color}; padding: 5px;"
                )
            )

    def _get_payment_method_label(self, mid: int, card_map: dict) -> str:
        return "Bank" if mid == _BANK_ACCOUNT_ID else card_map.get(mid, f"Card {mid}")

    def on_edit_balance(self) -> None:
        dialog = BalanceDialog(self, self.view_model.budget_service.get_bank_balance())
        if (
            dialog.exec() == BalanceDialog.Accepted
            and (balance := dialog.get_balance()) is not None
        ):
            self.view_model.budget_service.set_bank_balance(amount=balance)
            self.view_model.month_summary = (
                self.view_model.budget_service.get_month_summary(
                    year_month=self.view_model.current_month
                )
            )
            self._update_balance_display()
            self.view_model.month_summary_updated.emit(self.view_model.month_summary)

    def on_archive_month(self) -> None:
        self.view_model.budget_service.archive_month(
            year_month=self.view_model.current_month
        )

    def on_add_bill(self) -> None:
        dialog = BillDialog(
            self,
            None,
            payment_method_repo=self.view_model.budget_service.payment_method_repo,
            current_month=self.view_model.current_month,
        )
        if dialog.exec() == BillDialog.Accepted and (bill := dialog.get_bill()):
            self.view_model.add_bill(bill=bill)

    def _get_bill_from_row(self, row: int):
        if row < 0 or not self.view_model.month_summary:
            return None
        item = self.bills_table.item(row, 0)
        if item is None:
            return None
        bill_id = item.data(Qt.ItemDataRole.UserRole)
        return next(
            (b for b in self.view_model.month_summary.all_bills if b.id == bill_id),
            None,
        )

    def _get_income_from_row(self, row: int):
        if row < 0 or not self.view_model.month_summary:
            return None
        item = self.income_table.item(row, 0)
        if item is None:
            return None
        iid = item.data(Qt.ItemDataRole.UserRole)
        return next(
            (
                i
                for i in self.view_model.month_summary.all_income_sources
                if i.id == iid
            ),
            None,
        )

    def _on_bill_row_header_click(self, row: int) -> None:
        if self.read_only:
            return
        if bill := self._get_bill_from_row(row):
            self._edit_bill_dialog(bill)

    def _edit_bill_dialog(self, bill) -> None:
        had_override = bill.has_month_override
        dialog = BillDialog(
            self,
            bill,
            payment_method_repo=self.view_model.budget_service.payment_method_repo,
            current_month=self.view_model.current_month,
        )
        if dialog.exec() == BillDialog.Accepted and (eb := dialog.get_bill()):
            if dialog.month_only_check.isChecked():
                self.view_model.update_bill_for_month(bill=eb)
            else:
                if had_override:
                    self.view_model.delete_bill_month_override(bill_id=eb.id)
                self.view_model.update_bill(bill=eb)

    def on_delete_bill(self) -> None:
        rows = sorted({idx.row() for idx in self.bills_table.selectedIndexes()})
        ids = [b.id for r in rows if (b := self._get_bill_from_row(r)) is not None]
        if not ids:
            return
        count = len(ids)
        noun = "bill" if count == 1 else f"{count} bills"
        reply = QMessageBox.question(
            self,
            "Delete Bill",
            f"Permanently delete {noun}?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.view_model.delete_bills(bill_ids=ids)

    def on_add_income(self) -> None:
        dialog = IncomeDialog(self, None, current_month=self.view_model.current_month)
        if dialog.exec() == IncomeDialog.Accepted and (inc := dialog.get_income()):
            if dialog.month_only_check.isChecked():
                self.view_model.add_income_month_extra(income=inc)
            else:
                self.view_model.add_income(income=inc)

    def _on_income_row_header_click(self, row: int) -> None:
        if self.read_only:
            return
        if inc := self._get_income_from_row(row):
            self._edit_income_dialog(inc)

    def _edit_income_dialog(self, income) -> None:
        had_override = income.has_month_override
        dialog = IncomeDialog(self, income, current_month=self.view_model.current_month)
        if dialog.exec() == IncomeDialog.Accepted and (inc := dialog.get_income()):
            if income.is_month_only:
                self.view_model.update_income_month_extra(income=inc)
            elif dialog.month_only_check.isChecked():
                self.view_model.update_income_for_month(income=inc)
            else:
                if had_override:
                    self.view_model.delete_income_month_override(income_id=inc.id)
                self.view_model.update_income(income=inc)

    def on_delete_income(self) -> None:
        rows = sorted({idx.row() for idx in self.income_table.selectedIndexes()})
        incomes = [i for r in rows if (i := self._get_income_from_row(r)) is not None]
        if not incomes:
            return
        count = len(incomes)
        noun = "income source" if count == 1 else f"{count} income sources"
        reply = QMessageBox.question(
            self,
            "Delete Income",
            f"Permanently delete {noun}?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            extra_ids = [i.id for i in incomes if i.is_month_only]
            income_ids = [i.id for i in incomes if not i.is_month_only]
            for extra_id in extra_ids:
                self.view_model.delete_income_month_extra(extra_id=extra_id)
            if income_ids:
                self.view_model.delete_incomes(income_ids=income_ids)
