"""Delete flows for MonthView - extracted to stay under the LOC limit."""

from PySide6.QtWidgets import QMessageBox

from clear_budget.ui.utils.format_helpers import MONTH_NAMES


class MonthViewDeleteMixin:
    """Bill and income delete confirmation flows for MonthView."""

    def on_delete_bill(self) -> None:
        rows = sorted({idx.row() for idx in self.bills_table.selectedIndexes()})
        ids = [b.id for r in rows if (b := self._get_bill_from_row(r)) is not None]
        if not ids:
            return
        viewed = self.view_model.current_month
        viewed_name = MONTH_NAMES[viewed.month]
        noun = "bill" if len(ids) == 1 else f"{len(ids)} bills"
        scope = self._ask_delete_scope(noun, viewed_name)
        if scope == "stop":
            self.view_model.end_bills(
                bill_ids=ids, last_active_month=viewed.previous_month()
            )
        elif scope == "wipe":
            self.view_model.delete_bills(bill_ids=ids)

    def _ask_delete_scope(self, noun: str, viewed_name: str) -> str:
        """Ask how to delete: 'stop' (from viewed month on), 'wipe' (all), 'cancel'."""
        box = QMessageBox(self)
        box.setWindowTitle("Delete Bill")
        box.setText(
            f"Delete {noun}?\n\n"
            f"Stop from {viewed_name}: drops it from {viewed_name} onward and "
            f"keeps every earlier month unchanged.\n"
            f"Delete entirely: removes it from every month, including history. "
            f"This cannot be undone."
        )
        stop_btn = box.addButton(
            f"Stop from {viewed_name}", QMessageBox.ButtonRole.AcceptRole
        )
        wipe_btn = box.addButton(
            "Delete entirely", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(cancel_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is stop_btn:
            return "stop"
        if clicked is wipe_btn:
            return "wipe"
        return "cancel"

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
