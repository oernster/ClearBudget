"""Rules the Bill and Income dialogs share: reading the amount; the start month.

One home, so the two dialogs cannot drift apart again. They had: the bill
dialog started a new bill at the viewed month while the income dialog left a
new income unbounded, so it appeared in every month before it was added.

Qt-free on purpose. The dialogs mix this in; the tests borrow it onto a plain
stand-in, because this repository does not run a QApplication in its suite.
"""

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.shared.errors import InvalidAmountError
from clear_budget.ui.utils.amount_fields import AmountRefusalMixin, field_pence

_AMOUNT_LABEL = "Amount"


class EntryDialogRulesMixin(AmountRefusalMixin):
    """Amount reading for a dialog with an `amount_edit` line edit."""

    def _typed_amount(self) -> Amount:
        """The amount box as exact pence; raises InvalidAmountError."""
        return Amount(pence=field_pence(self.amount_edit, label=_AMOUNT_LABEL))

    def _amount_refusal(self) -> str | None:
        """Why the typed amount cannot be saved, worded for the user; or None."""
        try:
            self._typed_amount()
        except InvalidAmountError as refusal:
            return str(refusal)
        return None

    def _refuse_unreadable_amount(self) -> bool:
        """Say why the amount was refused and keep the dialog open.

        True when it was refused. The dialog stays open with everything the
        user typed, so only the amount needs correcting.
        """
        refusal = self._amount_refusal()
        if refusal is None:
            return False
        self._refuse_amount(self.amount_edit, refusal)
        return True


def entry_start_month(existing, viewed: YearMonth) -> YearMonth | None:
    """Where a saved entry starts.

    A new entry exists from the month it was added in, so it never appears
    in months before it. An edit keeps the start the entry already has, even
    None, since moving it would restate what earlier months reported.
    """
    return viewed if existing is None else existing.start_ym
