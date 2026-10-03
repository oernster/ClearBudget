"""Inline-edit handler mixin for MonthView - extracted to stay under LOC limit."""

import dataclasses
from typing import ClassVar

from PySide6.QtCore import Qt, QTimer

from clear_budget.shared.errors import InvalidAmountError, InvalidDueDayError
from clear_budget.ui.views._month_view_cell_edits import (
    BILL_AMOUNT_COL,
    BILL_CATEGORY_COL,
    BILL_DAY_COL,
    BILL_NAME_COL,
    INCOME_AMOUNT_COL,
    INCOME_DAY_COL,
    INCOME_NAME_COL,
    edited_bill,
    edited_income,
)

_CELL_REFUSED_TITLE = "Not saved"


class MonthViewEditMixin:
    """Inline cell-edit and checkbox handlers for MonthView."""

    _EDITABLE_BILL_COLS: ClassVar[set[int]] = {
        BILL_NAME_COL,
        BILL_AMOUNT_COL,
        BILL_CATEGORY_COL,
        BILL_DAY_COL,
    }
    _EDITABLE_INCOME_COLS: ClassVar[set[int]] = {
        INCOME_NAME_COL,
        INCOME_AMOUNT_COL,
        INCOME_DAY_COL,
    }

    def _on_bill_cell_clicked(self, row: int, col: int) -> None:
        if col not in (5, 6, 7):
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
                elif col == 6:
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if bill.skipped_for_month
                        else Qt.CheckState.Unchecked
                    )
                else:
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if bill.paid_for_month
                        else Qt.CheckState.Unchecked
                    )
                self.bills_table.blockSignals(False)
            return
        if bill is None:
            return
        if col == 5:
            self.view_model.set_bill_active(bill_id=bill.id, active=not bill.active)
        elif col == 6:
            if bill.skipped_for_month:
                self.view_model.unskip_bill_for_month(bill_id=bill.id)
            else:
                self.view_model.skip_bill_for_month(bill_id=bill.id)
        else:
            if bill.paid_for_month:
                self.view_model.unmark_bill_paid_for_month(bill_id=bill.id)
            else:
                self.view_model.mark_bill_paid_for_month(bill_id=bill.id)

    def _on_bill_item_changed(self, item) -> None:
        if item.column() not in self._EDITABLE_BILL_COLS:
            if item.column() not in (6, 7):
                QTimer.singleShot(0, self.view_model.refresh_month_summary)
            return
        bill = self._get_bill_from_row(item.row())
        if bill is None:
            return
        col, v = item.column(), item.text().strip()
        if col == BILL_AMOUNT_COL and bill.base_amount is not None:
            self._reject_inline_amount_edit(bill)
            return
        try:
            u = edited_bill(bill, col, v)
        except (InvalidAmountError, InvalidDueDayError) as refusal:
            self._refuse_cell_edit(refusal)
            return
        if u is None or u == bill:
            return
        QTimer.singleShot(0, lambda: self._inline_update_bill(bill, u))

    def _refuse_cell_edit(self, refusal: Exception) -> None:
        """Say why a typed cell cannot be saved, then put the cell back.

        The same shape as `_reject_inline_amount_edit`: a message naming the
        problem, then the table redrawn from what is stored.
        """
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(self, _CELL_REFUSED_TITLE, str(refusal))
        QTimer.singleShot(0, self.view_model.refresh_month_summary)

    @staticmethod
    def _own_amount(bill):
        """The bill as it must be WRITTEN, rather than as it is displayed.

        A bill listed for a month on or after a scheduled increase carries that
        month's amount in `amount` and its own in `base_amount`. Writing the
        displayed figure back would make the increase the new base and restate
        every earlier month, which is the one thing this feature exists to
        prevent. The dialog already guards this by editing `base_amount`; an
        inline edit of the name, category or day went straight past it.
        """
        if bill.base_amount is None:
            return bill
        return dataclasses.replace(bill, amount=bill.base_amount)

    def _reject_inline_amount_edit(self, bill) -> None:
        """Refuse an inline amount edit on a month a scheduled change governs.

        Typing over the figure is ambiguous here: it could mean either that
        this month cost something else or that the standing amount has moved
        again. Rather than guess, say where the amount lives and put the cell
        back.
        """
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(
            self,
            "Amount is scheduled",
            f"'{bill.name}' has a scheduled amount change, so this month's"
            " figure comes from that schedule.\n\nOpen the bill and use the"
            " Amount changes section to alter it or use 'This month only'"
            " for a one-off difference.",
        )
        QTimer.singleShot(0, self.view_model.refresh_month_summary)

    def _inline_update_bill(self, before, after) -> None:
        self.view_model.update_bill(bill=self._own_amount(after))
        self._offer_apply_edited_bill(before, after)

    def _inline_update_income(self, before, after) -> None:
        if before.is_month_only:
            self.view_model.update_income_month_extra(income=after)
        else:
            self.view_model.update_income(income=after)
        self._offer_apply_edited_income(before, after)

    def _on_income_item_changed(self, item) -> None:
        if item.column() in (2, 4, 5, 6):
            return
        if item.column() not in self._EDITABLE_INCOME_COLS:
            QTimer.singleShot(0, self.view_model.refresh_month_summary)
            return
        inc = self._get_income_from_row(item.row())
        if inc is None:
            return
        try:
            u = edited_income(inc, item.column(), item.text().strip())
        except (InvalidAmountError, InvalidDueDayError) as refusal:
            self._refuse_cell_edit(refusal)
            return
        if u is None or u == inc:
            return
        QTimer.singleShot(0, lambda: self._inline_update_income(inc, u))

    def _on_income_cell_clicked(self, row: int, col: int) -> None:
        if col not in (2, 4, 5, 6):
            return
        from PySide6.QtWidgets import QApplication

        mods = QApplication.keyboardModifiers()
        inc = self._get_income_from_row(row)
        if col in (5, 6):
            self._on_income_skip_received_clicked(row, col, inc, mods)
            return
        if mods & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            return
        if inc is None:
            return
        if col == 2:
            updated = dataclasses.replace(inc, is_reliable=not inc.is_reliable)
            if inc.is_month_only:
                QTimer.singleShot(
                    0,
                    lambda: self.view_model.update_income_month_extra(income=updated),
                )
            else:
                QTimer.singleShot(
                    0, lambda: self.view_model.update_income(income=updated)
                )
        elif not inc.is_month_only:
            QTimer.singleShot(
                0,
                lambda: self.view_model.update_income(
                    income=dataclasses.replace(inc, active=not inc.active)
                ),
            )

    def _on_income_skip_received_clicked(self, row: int, col: int, inc, mods) -> None:
        if mods & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            item = self.income_table.item(row, col)
            if item and inc:
                self.income_table.blockSignals(True)
                if col == 5:
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if inc.skipped_for_month
                        else Qt.CheckState.Unchecked
                    )
                else:
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if inc.received_for_month
                        else Qt.CheckState.Unchecked
                    )
                self.income_table.blockSignals(False)
            return
        if inc is None:
            return
        if col == 5:
            if inc.is_month_only:
                return
            if inc.skipped_for_month:
                self.view_model.unskip_income_for_month(income_id=inc.id)
            else:
                self.view_model.skip_income_for_month(income_id=inc.id)
        elif inc.is_month_only:
            if inc.received_for_month:
                self.view_model.unmark_income_extra_received(extra_id=inc.id)
            else:
                self.view_model.mark_income_extra_received(extra_id=inc.id)
        else:
            if inc.received_for_month:
                self.view_model.unmark_income_received_for_month(income_id=inc.id)
            else:
                self.view_model.mark_income_received_for_month(income_id=inc.id)
