"""Promoting a one-off income entry to a recurring source.

A one-off lives in `income_month_extras` and a recurring source lives in
`income_sources`, so the change is a delete plus an add across two tables
rather than an update. It confirms first; it names the consequence rather
than asking a bare "are you sure".

Only this direction exists. The reverse, turning a recurring income into a
one-off, would delete the source and so remove it from months it really did
arrive in. The app does not rewrite history. An income that stops names
its final month instead (`ends_check` in the income dialog), which leaves
every month before it exactly as it was.
"""

from PySide6.QtWidgets import QMessageBox

from clear_budget.ui.utils.format_helpers import MONTH_NAMES


class MonthViewIncomeConvertMixin:
    """Promotion of a one-off income entry to a recurring source."""

    def _convert_month_label(self) -> str:
        """The month being viewed, named rather than numbered."""
        ym = self.view_model.current_month
        return f"{MONTH_NAMES[ym.month]} {ym.year}"

    def _confirm_income_promotion(self, *, name: str) -> bool:
        """Ask before turning a one-off into a recurring income."""
        month = self._convert_month_label()
        reply = QMessageBox.question(
            self,
            "Make this a regular income?",
            f"'{name}' currently exists in {month} alone.\n\n"
            "Making it regular means it arrives every month from now on.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _promote_income(self, *, before, after):
        """Turn the one-off `before` into a recurring source, once confirmed.

        Returns the persisted source; None when the user declines, so the
        caller can tell a completed promotion from an abandoned one.
        """
        if not self._confirm_income_promotion(name=after.name):
            return None
        return self.view_model.convert_income_extra_to_source(
            extra_id=before.id, income=after
        )
