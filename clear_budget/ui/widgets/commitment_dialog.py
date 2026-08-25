"""Add or edit one commitment.

Follows the bill dialog's shape: the fields, then a note saying what OK will
do before it is pressed. A commitment is money held back rather than money
moved, so the note says so plainly and the dialog stores nothing else.
"""

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from clear_budget.domain.entities.commitment import Commitment
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.recurrence import Recurrence
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui.widgets.first_stop_dialog import FirstStopDialog
from clear_budget.ui.widgets.themed_combo_box import ThemedComboBox

_DIALOG_MIN_WIDTH_PX = 420
# The repeats a user can pick, as (label, interval in months). Every one is a
# real interval; "Once" is the absence of one.
_REPEAT_CHOICES = (
    ("Once", None),
    ("Monthly", 1),
    ("Every 3 months", 3),
    ("Every 6 months", 6),
    ("Annually", 12),
)
_DEFAULT_REPEAT_INDEX = 4


class CommitmentDialog(FirstStopDialog):
    """Collects one obligation to reserve for."""

    def __init__(self, parent=None, commitment: Commitment | None = None) -> None:
        super().__init__(parent)
        self._existing = commitment
        self.setWindowTitle("Edit commitment" if commitment else "Add a commitment")
        self.setMinimumWidth(ui_scale.px(_DIALOG_MIN_WIDTH_PX))
        self._build_ui()
        if commitment is not None:
            self._fill_from(commitment)

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Car insurance")
        form.addRow("Name", self.name_edit)

        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("0.00")
        form.addRow("Amount", self.amount_edit)

        self.due_edit = QDateEdit()
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDate(QDate.currentDate().addMonths(1))
        form.addRow("Due", self.due_edit)

        self.repeat_combo = ThemedComboBox()
        for label, _months in _REPEAT_CHOICES:
            self.repeat_combo.addItem(label)
        self.repeat_combo.setCurrentIndex(_DEFAULT_REPEAT_INDEX)
        form.addRow("Repeats", self.repeat_combo)

        self.held_edit = QLineEdit()
        self.held_edit.setPlaceholderText("0.00")
        form.addRow("Already put by", self.held_edit)

        layout.addLayout(form)

        note = QLabel(
            "Nothing is moved and no separate account is assumed. This only"
            " holds the money back from what the app calls spendable."
        )
        note.setObjectName(label_roles.BODY_DETAIL)
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setDefault(True)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setAutoDefault(False)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _fill_from(self, commitment: Commitment) -> None:
        """Show an existing commitment's own figures."""
        self.name_edit.setText(commitment.name)
        self.amount_edit.setText(f"{commitment.amount.pence / 100:.2f}")
        due = commitment.due_date
        self.due_edit.setDate(QDate(due.year, due.month, due.day))
        months = commitment.recurrence.months
        for index, (_label, choice) in enumerate(_REPEAT_CHOICES):
            if choice == months:
                self.repeat_combo.setCurrentIndex(index)
                break
        self.held_edit.setText(f"{commitment.already_held.pence / 100:.2f}")

    def commitment(self, *, today: date | None = None) -> Commitment:
        """The commitment as entered.

        Raises:
            ValueError: If the amount or the held figure is not a number.
        """
        day = today if today is not None else date.today()  # noqa: DTZ011
        qdate = self.due_edit.date()
        months = _REPEAT_CHOICES[self.repeat_combo.currentIndex()][1]
        existing = self._existing
        return Commitment(
            id=existing.id if existing else 0,
            name=self.name_edit.text().strip(),
            amount=Amount(pence=_pence(self.amount_edit.text())),
            due_date=date(qdate.year(), qdate.month(), qdate.day()),
            recurrence=Recurrence(months=months),
            created_month=(
                existing.created_month
                if existing
                else YearMonth(year=day.year, month=day.month)
            ),
            already_held=Amount(pence=_pence(self.held_edit.text())),
            category=existing.category if existing else None,
            active=existing.active if existing else True,
            final_month=existing.final_month if existing else None,
        )


def _pence(text: str) -> int:
    """A typed money figure as pence; an empty field is nothing put by."""
    cleaned = text.strip()
    if not cleaned:
        return 0
    return round(float(cleaned) * 100)
