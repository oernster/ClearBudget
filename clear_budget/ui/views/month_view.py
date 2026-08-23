"""Month budget view widget - displays bills and income for selected month."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from clear_budget.ui.utils.format_helpers import (
    MONTH_NAMES,
    apply_nav_label_color,
)
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.views._month_view_apply_prompt import MonthViewApplyPromptMixin
from clear_budget.ui.views._month_view_balance_mixin import MonthViewBalanceMixin
from clear_budget.ui.utils.tab_icons import ring_tab_stops
from clear_budget.ui.views._month_view_builders import MonthViewBuilderMixin
from clear_budget.ui.views._month_view_delete_mixin import MonthViewDeleteMixin
from clear_budget.ui.views._month_view_edit_mixin import MonthViewEditMixin
from clear_budget.ui.views._month_view_income_convert import (
    MonthViewIncomeConvertMixin,
)
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


class MonthView(
    MonthViewBalanceMixin,
    MonthViewBuilderMixin,
    MonthViewTableMixin,
    MonthViewEditMixin,
    MonthViewDeleteMixin,
    MonthViewApplyPromptMixin,
    MonthViewIncomeConvertMixin,
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

    def _get_payment_method_label(self, mid: int, card_map: dict) -> str:
        return "Bank" if mid == _BANK_ACCOUNT_ID else card_map.get(mid, f"Card {mid}")

    def on_show_graph(self) -> None:
        """Open the month graph for the viewed month's bank balance."""
        from clear_budget.ui.widgets.month_graph_dialog import MonthGraphDialog

        if self.view_model.month_summary is None:
            return
        svc = self.view_model.budget_service

        def series_for(ym):
            """The bank series for `ym`, derived fresh so navigation is live."""
            summary = svc.get_month_summary(year_month=ym)
            series = svc.get_bank_graph_series(year_month=ym, summary=summary)
            return f"{MONTH_NAMES[ym.month]} {ym.year}: bank balance by day", [series]

        MonthGraphDialog(
            self,
            series_for=series_for,
            start_month=self.view_model.current_month,
            base_month=self.view_model.base_month,
            budget_service=svc,
            anchor_month=self.view_model.current_month,
            overdraft_limit_pence=svc.get_overdraft_limit().pence,
        ).exec()

    def nav_targets(self) -> list:
        """Ordered keyboard-ring stops for this tab.

        READING order, which with two stacked trays means the TOP tray first
        and the lower one after it, each left to right as drawn. A ring that
        disagrees with the drawing does not present as a wrong order, it
        presents as a SKIPPED control: the user tabs past where a button
        visibly is and lands somewhere else entirely.

        The tab being shown is not in the list. It is a stop that could do
        nothing, dropped here rather than disabled, because a
        disabled control paints the permanent red ring and would read as
        broken rather than as current.
        """
        # Archive was moved out of the tab run to the right-hand group,
        # so the ring has to walk it there. A ring that disagrees with the
        # drawing reads as a SKIPPED control, not as a wrong order.
        others = ring_tab_stops(self.tab_btns[:-1])
        archive_stop = ring_tab_stops(self.tab_btns[-1:])
        return [
            self.prev_btn,
            self.next_btn,
            self.load_btn,
            self.save_btn,
            self.budgets_btn,
            self.settings_btn,
            self.bank_btn,
            *others,
            self.graph_btn,
            *archive_stop,
            self.theme_btn,
            self.info_btn,
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
            if dialog.one_off_check.isChecked():
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
        if dialog.exec() != IncomeDialog.Accepted:
            return
        inc = dialog.get_income()
        if inc is None:
            return
        # The dialog reports the identity the box asks for. The box is only
        # offered on a one-off, so the single mismatch it can produce is a
        # request to promote; there is no demote direction to route.
        if income.is_month_only and not inc.is_month_only:
            if (promoted := self._promote_income(before=income, after=inc)) is None:
                return
            self._offer_apply_edited_income(income, promoted)
            return
        if income.is_month_only:
            self.view_model.update_income_month_extra(income=inc)
        elif dialog.scope_check.isChecked():
            self.view_model.update_income_for_month(income=inc)
        else:
            if had_override:
                self.view_model.delete_income_month_override(income_id=inc.id)
            self.view_model.update_income(income=inc)
        self._offer_apply_edited_income(income, inc)
