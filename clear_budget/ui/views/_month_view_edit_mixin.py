"""Inline-edit handler mixin for MonthView - extracted to stay under LOC limit."""

import dataclasses

from PySide6.QtCore import Qt, QTimer

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.shared.currency import get_symbol


class MonthViewEditMixin:
    """Inline cell-edit and checkbox handlers for MonthView."""

    _EDITABLE_BILL_COLS = {0, 1, 2, 4}
    _EDITABLE_INCOME_COLS = {0, 1, 3}

    def _on_bill_cell_clicked(self, row: int, col: int) -> None:
        if col not in (5, 6):
            return
        from PySide6.QtWidgets import QApplication

        mods = QApplication.keyboardModifiers()
        bill = self._get_bill_from_row(row)
        if mods & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            item = self.bills_table.item(row, col)
            if item and bill:
                self.bills_table.blockSignals(True)
                if col == 5:
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if bill.active
                        else Qt.CheckState.Unchecked
                    )
                else:
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if bill.skipped_for_month
                        else Qt.CheckState.Unchecked
                    )
                self.bills_table.blockSignals(False)
            return
        if bill is None:
            return
        if col == 5:
            self.view_model.set_bill_active(bill_id=bill.id, active=not bill.active)
        else:
            if bill.skipped_for_month:
                self.view_model.unskip_bill_for_month(bill_id=bill.id)
            else:
                self.view_model.skip_bill_for_month(bill_id=bill.id)

    def _on_bill_item_changed(self, item) -> None:
        if item.column() not in self._EDITABLE_BILL_COLS:
            if item.column() != 6:
                QTimer.singleShot(0, self.view_model.refresh_month_summary)
            return
        bill = self._get_bill_from_row(item.row())
        if bill is None:
            return
        col, v = item.column(), item.text().strip()
        try:
            if col == 0:
                u = dataclasses.replace(bill, name=v or bill.name)
            elif col == 1:
                u = dataclasses.replace(
                    bill, amount=Amount.from_pounds(float(v.lstrip(get_symbol())))
                )
            elif col == 2:
                u = dataclasses.replace(bill, category=v.lower().replace(" ", "_"))
            elif col == 4:
                u = dataclasses.replace(bill, day_of_month=int(v))
            else:
                return
            if u == bill:
                return
            QTimer.singleShot(0, lambda: self.view_model.update_bill(bill=u))
        except (ValueError, AttributeError):
            QTimer.singleShot(0, self.view_model.refresh_month_summary)

    def _on_income_item_changed(self, item) -> None:
        if item.column() in (2, 4):
            return
        if item.column() not in self._EDITABLE_INCOME_COLS:
            QTimer.singleShot(0, self.view_model.refresh_month_summary)
            return
        inc = self._get_income_from_row(item.row())
        if inc is None:
            return
        col, v = item.column(), item.text().strip()
        try:
            if col == 0:
                u = dataclasses.replace(inc, name=v or inc.name)
            elif col == 1:
                u = dataclasses.replace(
                    inc, amount=Amount.from_pounds(float(v.lstrip(get_symbol())))
                )
            elif col == 3:
                u = dataclasses.replace(
                    inc, day_of_month=int(v) if v.isdigit() else None
                )
            else:
                return
            if u == inc:
                return
            QTimer.singleShot(0, lambda: self.view_model.update_income(income=u))
        except (ValueError, AttributeError):
            QTimer.singleShot(0, self.view_model.refresh_month_summary)

    def _on_income_cell_clicked(self, row: int, col: int) -> None:
        if col not in (2, 4):
            return
        from PySide6.QtWidgets import QApplication

        mods = QApplication.keyboardModifiers()
        if mods & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            return
        inc = self._get_income_from_row(row)
        if inc is None:
            return
        if col == 2:
            QTimer.singleShot(
                0,
                lambda: self.view_model.update_income(
                    income=dataclasses.replace(inc, is_reliable=not inc.is_reliable)
                ),
            )
        else:
            QTimer.singleShot(
                0,
                lambda: self.view_model.update_income(
                    income=dataclasses.replace(inc, active=not inc.active)
                ),
            )
