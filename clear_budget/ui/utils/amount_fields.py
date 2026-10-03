"""Reading a typed money field (or refusing it) the same way on every screen.

Every amount a person types goes through `pence_from_text`, so nothing rounds
away between the figure typed and the figure stored. A figure it will not read
exactly is refused with the parser's own message, named for the field, through
`AmountRefusalMixin._refuse_amount`: a warning, then the field is focused and
selected so only it needs correcting. A dialog stays open; nothing is saved.

Qt-free at import, so the reading rules can be tested without a QApplication;
only the warning itself touches Qt.
"""

from clear_budget.application.formatting import pence_from_text
from clear_budget.shared.errors import InvalidAmountError

AMOUNT_REFUSED_TITLE = "Amount not accepted"
# The Reserves and Recommendations views edit the same stored buffer.
BUFFER_LABEL = "Buffer"


class _Required:
    """Marks a field that must not be left empty."""


REQUIRED = _Required()


class AmountFieldRefused(InvalidAmountError):
    """A typed field that cannot be saved; carries the field to put focus on."""

    def __init__(self, field, message: str) -> None:
        super().__init__(message)
        self.field = field


def field_pence(field, *, label: str, when_empty=REQUIRED, signed: bool = False):
    """The field's text as exact pence; `when_empty` when it was left blank.

    Raises AmountFieldRefused, its message prefixed with `label`, for anything
    `pence_from_text` refuses (including a blank REQUIRED field).
    """
    text = field.text().strip()
    if not text and when_empty is not REQUIRED:
        return when_empty
    try:
        return pence_from_text(text, signed=signed)
    except InvalidAmountError as refusal:
        raise AmountFieldRefused(field, f"{label}: {refusal}") from None


class AmountRefusalMixin:
    """The one way a screen says a typed amount was refused."""

    def _refuse_amount(self, field, refusal) -> None:
        """Warn, then put the cursor in the field so it can be corrected.

        The field's signals are held while the warning is up: a view saves on
        `editingFinished`, which the warning taking focus could fire again.
        """
        from PySide6.QtWidgets import QMessageBox

        was_blocked = field.blockSignals(True)
        try:
            QMessageBox.warning(self, AMOUNT_REFUSED_TITLE, str(refusal))
        finally:
            field.blockSignals(was_blocked)
        field.setFocus()
        field.selectAll()
