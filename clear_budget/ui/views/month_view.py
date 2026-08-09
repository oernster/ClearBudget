"""Month budget view widget - displays bills and income for selected month."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from clear_budget.domain.services.bank_cashflow import BankCashflowService
from clear_budget.ui import label_roles
from clear_budget.ui.utils.format_helpers import (
    MONTH_NAMES,
    apply_nav_label_color,
    fmt,
)
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.views._month_view_apply_prompt import MonthViewApplyPromptMixin
from clear_budget.ui.views._month_view_builders import MonthViewBuilderMixin
from clear_budget.ui.views._month_view_delete_mixin import MonthViewDeleteMixin
from clear_budget.ui.views._month_view_edit_mixin import MonthViewEditMixin
from clear_budget.ui.views._month_view_table_mixin import (
    _BANK_ACCOUNT_ID,
    MonthViewTableMixin,
)
from clear_budget.ui.widgets.balance_dialog import BalanceDialog
from clear_budget.ui.widgets.bill_dialog import BillDialog
from clear_budget.ui.widgets.income_dialog import IncomeDialog

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

# A projected balance below this is shown as thin rather than healthy: one
# hundred pounds of headroom, in pence.
_THIN_BALANCE_PENCE = 10000


class MonthView(
    MonthViewBuilderMixin,
    MonthViewTableMixin,
    MonthViewEditMixin,
    MonthViewDeleteMixin,
    MonthViewApplyPromptMixin,
    QWidget,
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

    def set_nav_label_color(self, color: str) -> None:
        """Recolour the nav month label to match the Solvency tab."""
        apply_nav_label_color(self.month_label, color)

    def restyle(self) -> None:
        """Repaint the row colours set in code after a theme switch."""
        if self.view_model.month_summary:
            self.update_bills_table(self.view_model.month_summary)

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

    def _get_balance_role(self, p: int) -> str:
        """Severity role for a balance: negative, thin, or healthy."""
        if p < 0:
            return label_roles.DANGER
        return label_roles.WARN if p < _THIN_BALANCE_PENCE else label_roles.GOOD

    def _update_balance_display(self) -> None:
        if summary := self.view_model.month_summary:
            from datetime import datetime as _dt

            from clear_budget.domain.value_objects.year_month import YearMonth as _YM

            now = _dt.now()  # noqa: DTZ005 (app runs on naive local time)
            today_ym = _YM(now.year, now.month)
            if self.view_model.current_month == today_ym:
                # Elapsed dated bills/income are folded into the stored
                # balance at midnight (and at startup), so it is shown as-is.
                pence = self.view_model.budget_service.get_bank_balance().pence
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
            label_roles.set_role(self.balance_label, self._get_balance_role(pence))
            self._update_overdraft_warning(summary)

    def _update_overdraft_warning(self, summary) -> None:
        svc = self.view_model.budget_service
        projection = svc.get_month_cashflow_projection(
            year_month=self.view_model.current_month, summary=summary
        )
        overdraft_limit_pence = svc.get_overdraft_limit().pence
        severity = projection.overdraft_severity(overdraft_limit_pence)
        if severity == "none":
            self.overdraft_warning_label.setVisible(False)
            return

        low = fmt(abs(projection.min_balance_pence))
        day = projection.min_balance_day
        if severity == "amber":
            text = (
                f"⚠ Balance dips to -{low} around day {day} (covered by your overdraft)"
            )
            daily_interest = (
                BankCashflowService.estimate_daily_overdraft_interest_pence(
                    abs(projection.min_balance_pence),
                    svc.get_overdraft_apr_basis_points(),
                )
            )
            if daily_interest > 0:
                text += f" - ~{fmt(daily_interest)}/day interest"
            role = label_roles.WARN_NOTE
        elif overdraft_limit_pence > 0:
            text = (
                f"⚠ Balance may EXCEED your overdraft limit (-{low} around day {day})"
            )
            role = label_roles.DANGER_NOTE
        else:
            text = (
                f"⚠ Balance may go OVERDRAWN to -{low} around day {day}"
                " - no overdraft facility set"
            )
            role = label_roles.DANGER_NOTE

        self.overdraft_warning_label.setText(text)
        label_roles.set_role(self.overdraft_warning_label, role)
        self.overdraft_warning_label.setVisible(True)

    def _get_payment_method_label(self, mid: int, card_map: dict) -> str:
        return "Bank" if mid == _BANK_ACCOUNT_ID else card_map.get(mid, f"Card {mid}")

    def on_show_graph(self) -> None:
        """Open the month graph for the viewed month's bank balance."""
        from clear_budget.ui.widgets.month_graph_dialog import MonthGraphDialog

        summary = self.view_model.month_summary
        if summary is None:
            return
        ym = self.view_model.current_month
        series = self.view_model.budget_service.get_bank_graph_series(
            year_month=ym, summary=summary
        )
        MonthGraphDialog(
            self,
            title=f"{MONTH_NAMES[ym.month]} {ym.year}: bank balance by day",
            series=[series],
            month_label=f"{MONTH_NAMES[ym.month]} {ym.year}",
            budget_service=self.view_model.budget_service,
            anchor_month=ym,
        ).exec()

    def nav_targets(self) -> list:
        """Ordered keyboard-ring stops for this tab."""
        return [
            self.load_btn,
            self.save_btn,
            self.graph_btn,
            self.prev_btn,
            self.next_btn,
            self.theme_btn,
            self.edit_balance_btn,
            self.bills_table,
            self.add_bill_btn,
            self.delete_bill_btn,
            self.income_table,
            self.add_income_btn,
            self.delete_income_btn,
        ]

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

    def on_add_bill(self) -> None:
        dialog = BillDialog(
            self,
            None,
            payment_method_repo=self.view_model.budget_service.payment_method_repo,
            current_month=self.view_model.current_month,
        )
        if dialog.exec() == BillDialog.Accepted and (bill := dialog.get_bill()):
            persisted = self.view_model.add_bill(bill=bill)
            self._save_amount_changes(persisted.id, dialog)
            self._offer_apply_new_bill(persisted)

    def _save_amount_changes(self, bill_id: int, dialog: BillDialog) -> None:
        """Persist the scheduled amount changes the dialog is holding.

        Done after the bill is saved, because a new bill has no id until then.
        """
        self.view_model.budget_service.set_bill_amount_changes(
            bill_id=bill_id, changes=dialog.get_amount_changes()
        )

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
        is_month_only = item.data(Qt.ItemDataRole.UserRole + 1)
        return next(
            (
                i
                for i in self.view_model.month_summary.all_income_sources
                if i.id == iid and i.is_month_only == is_month_only
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
                self._save_amount_changes(eb.id, dialog)
            self._offer_apply_edited_bill(bill, eb)

    def on_add_income(self) -> None:
        dialog = IncomeDialog(self, None, current_month=self.view_model.current_month)
        if dialog.exec() == IncomeDialog.Accepted and (inc := dialog.get_income()):
            if dialog.month_only_check.isChecked():
                persisted = self.view_model.add_income_month_extra(income=inc)
            else:
                persisted = self.view_model.add_income(income=inc)
            self._offer_apply_new_income(persisted)

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
            self._offer_apply_edited_income(income, inc)
