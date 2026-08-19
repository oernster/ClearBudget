"""Conversions between a one-off income entry and a recurring income source.

A one-off lives in `income_month_extras` and a recurring source lives in
`income_sources`, so converting either way destroys a row in one table and
creates one in the other. Both directions therefore confirm first; both name
the consequence rather than asking a bare "are you sure".

The demotion warning is the one that matters. An income source carries no end
month, unlike a bill, so it exists in every month there is. Turning one into a
one-off removes it from all of them, past included. That makes this a poor way
to record "my salary stopped in September". The wording says so rather than
letting the figure quietly vanish from months already reconciled.
"""

from PySide6.QtWidgets import QMessageBox

from clear_budget.ui.utils.format_helpers import MONTH_NAMES


class MonthViewIncomeConvertMixin:
    """Conversion between a one-off and a recurring income, both directions."""

    def _convert_month_label(self) -> str:
        """The month being viewed, named rather than numbered."""
        ym = self.view_model.current_month
        return f"{MONTH_NAMES[ym.month]} {ym.year}"

    def _confirm_income_conversion(self, *, name: str, to_one_off: bool) -> bool:
        """Ask before moving an income entry between the two kinds."""
        month = self._convert_month_label()
        if to_one_off:
            title = "Make this a one-off?"
            body = (
                f"'{name}' is a regular income arriving every month.\n\n"
                f"Making it a {month} one-off removes it from every other "
                "month, past and future.\n\n"
                "This cannot be undone."
            )
        else:
            title = "Make this a regular income?"
            body = (
                f"'{name}' currently exists in {month} alone.\n\n"
                "Making it regular means it arrives every month from now on."
            )
        reply = QMessageBox.question(
            self,
            title,
            body,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _convert_income(self, *, before, after):
        """Convert `before` to the kind `after` asks for, once confirmed.

        Returns the persisted entry; None when the user declines, so the
        caller can tell a completed conversion from an abandoned one.
        """
        if not self._confirm_income_conversion(
            name=after.name, to_one_off=after.is_month_only
        ):
            return None
        if after.is_month_only:
            return self.view_model.convert_income_source_to_extra(
                income_id=before.id, income=after
            )
        return self.view_model.convert_income_extra_to_source(
            extra_id=before.id, income=after
        )
