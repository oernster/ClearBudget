"""Same-day balance-update prompt for newly added bills/income.

Dated bank transactions are normally applied to the balance at local
midnight on their due day. An item added ON its due day has already missed
that midnight, so the user is asked whether to apply it now; they may have
set the balance by hand already and not want it touched. Yes applies the
amount and marks the item paid/received; No leaves everything as entered.
"""

from datetime import date

from PySide6.QtWidgets import QMessageBox

from clear_budget.ui.utils.format_helpers import fmt
from clear_budget.ui.views._month_view_table_mixin import _BANK_ACCOUNT_ID


class MonthViewApplyPromptMixin:
    """Offers to apply a just-added same-day bill/income to the bank balance."""

    def _added_for_today(self, day_of_month: int | None) -> bool:
        """Whether the item is dated today in the real current month."""
        today = date.today()  # noqa: DTZ011 (due days are local-calendar days)
        viewed = self.view_model.current_month
        if (viewed.year, viewed.month) != (today.year, today.month):
            return False
        return day_of_month == today.day

    def _ask_apply_now(self, text: str) -> bool:
        reply = QMessageBox.question(
            self,
            "Update Balance?",
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _offer_apply_new_bill(self, bill) -> None:
        """Offer to deduct a bank bill added for today from the balance."""
        if bill is None or bill.payment_method_id != _BANK_ACCOUNT_ID:
            return
        if not self._added_for_today(bill.day_of_month):
            return
        if not self._ask_apply_now(
            f"'{bill.name}' is due today.\n\n"
            f"Deduct {fmt(bill.amount.pence)} from your bank balance now?\n\n"
            "Choose No if your balance already reflects this payment."
        ):
            return
        self.view_model.budget_service.apply_bill_to_balance_now(
            bill=bill, year_month=self.view_model.current_month
        )
        self.view_model.refresh_month_summary()

    def _offer_apply_edited_bill(self, before, after) -> None:
        """Offer to apply a bill whose due day was just edited to today.

        An edit that lands on today is treated like adding the bill dated
        today. No offer when the day was already today (it was considered
        then) or when the bill was already paid or skipped for the month.
        """
        if before is None:
            return
        if self._added_for_today(before.day_of_month):
            return
        if before.paid_for_month or before.skipped_for_month:
            return
        self._offer_apply_new_bill(after)

    def _offer_apply_edited_income(self, before, after) -> None:
        """Offer to apply an income whose day was just edited to today."""
        if before is None:
            return
        if self._added_for_today(before.day_of_month):
            return
        if before.received_for_month or before.skipped_for_month:
            return
        self._offer_apply_new_income(after)

    def _offer_apply_new_income(self, income) -> None:
        """Offer to add an income entry added for today to the balance."""
        if income is None or not self._added_for_today(income.day_of_month):
            return
        if not self._ask_apply_now(
            f"'{income.name}' arrives today.\n\n"
            f"Add {fmt(income.amount.pence)} to your bank balance now?\n\n"
            "Choose No if your balance already reflects this income."
        ):
            return
        self.view_model.budget_service.apply_income_to_balance_now(
            income=income, year_month=self.view_model.current_month
        )
        self.view_model.refresh_month_summary()
