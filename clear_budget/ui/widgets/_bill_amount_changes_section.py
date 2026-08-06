"""The "amount changes from" section of the bill dialog.

Its own module rather than part of `bill_dialog.py`, which is at 286 lines and
would land in the 381 to 399 danger band with this inline.

Mirrors the credit card dialog's scheduled-limit-changes section, at month
granularity. The user says what a bill costs from a month onward; earlier
months keep what they actually cost, which is the rule the domain enforces in
`bill_amount_schedule`.
"""

from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.bill_amount_change import BillAmountChange
from clear_budget.shared.errors import InvalidBillAmountChangeError
from clear_budget.ui.utils.format_helpers import MONTH_NAMES

# Matches the end-month field above it, which reads "August 2026".
_MONTH_FORMAT = "MMMM yyyy"
_FIRST_OF_MONTH = 1

# Sized to its content rather than left to the layout, which squeezed the field
# to 56px inside this dialog and clipped anything past three digits. The string
# is a measuring stick, not a limit: it is the widest amount worth planning for,
# and the width comes from the font, so it holds at any scale or font size.
_WIDEST_AMOUNT_SAMPLE = "123456.78"

# The longest month name, so the dropdown never has to squeeze its own text
# against the calendar button. September is the longest in English.
_WIDEST_MONTH_SAMPLE = "September 2026"


def _date_width(field: QDateEdit, sample: str) -> int:
    """Width `field` needs to show `sample` beside its calendar button.

    The chrome is derived from the widget itself, by taking what its own size
    hint allows beyond the text it is currently showing, so the calendar
    button, the frame and the spacing are all accounted for without any of
    them being guessed at.
    """
    metrics = field.fontMetrics()
    chrome = field.sizeHint().width() - metrics.horizontalAdvance(field.text())
    # One character of the font's own width as breathing room, so the longest
    # month does not sit flush against the calendar button.
    return metrics.horizontalAdvance(sample) + chrome + metrics.averageCharWidth()


def _text_width(field: QLineEdit, sample: str) -> int:
    """Width `field` needs to show `sample` without clipping it.

    The chrome (frame, text margins and room for the cursor) is read off the
    widget rather than guessed, so this holds when the font or the display
    scaling changes.
    """
    margins = field.textMargins()
    chrome = (
        field.contentsMargins().left()
        + field.contentsMargins().right()
        + margins.left()
        + margins.right()
        + field.fontMetrics().averageCharWidth()
    )
    return field.fontMetrics().horizontalAdvance(sample) + chrome


class BillAmountChangesSectionMixin:
    """Recording and removing a bill's scheduled amount changes."""

    def _build_amount_changes_section(self) -> QGroupBox:
        """Build the group box, wired to this dialog's in-memory list."""
        box = QGroupBox("Amount changes")
        outer = QVBoxLayout()

        explain = QLabel(
            "Set what this bill costs from a month onward, for a rent increase"
            " say. Months before it keep the amount they actually had."
        )
        explain.setWordWrap(True)
        # A word-wrapped label reports a single line as its height hint, so in a
        # vertical layout it gets squeezed and the wrapped text is clipped. This
        # lets it claim the height the wrapping actually needs.
        explain.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding
        )
        outer.addWidget(explain)

        self.amount_changes_list_layout = QVBoxLayout()
        outer.addLayout(self.amount_changes_list_layout)

        entry = QHBoxLayout()
        entry.addWidget(QLabel("From"))
        self.change_month_edit = QDateEdit()
        self.change_month_edit.setDisplayFormat(_MONTH_FORMAT)
        self.change_month_edit.setCalendarPopup(True)
        self.change_month_edit.setDate(
            QDate(self.current_month.year, self.current_month.month, _FIRST_OF_MONTH)
        )
        self.change_month_edit.setMinimumWidth(
            _date_width(self.change_month_edit, _WIDEST_MONTH_SAMPLE)
        )
        entry.addWidget(self.change_month_edit)
        entry.addWidget(QLabel("costs"))
        self.change_amount_edit = QLineEdit()
        self.change_amount_edit.setPlaceholderText("0.00")
        self.change_amount_edit.setMinimumWidth(
            _text_width(self.change_amount_edit, _WIDEST_AMOUNT_SAMPLE)
        )
        entry.addWidget(self.change_amount_edit)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._on_add_amount_change)
        entry.addWidget(add_btn)
        outer.addLayout(entry)

        self.change_warning_label = QLabel()
        self.change_warning_label.setVisible(False)
        self.change_warning_label.setWordWrap(True)
        outer.addWidget(self.change_warning_label)

        box.setLayout(outer)
        self._rebuild_amount_changes_list()
        return box

    def _rebuild_amount_changes_list(self) -> None:
        """Redraw the list from the in-memory model."""
        while self.amount_changes_list_layout.count():
            taken = self.amount_changes_list_layout.takeAt(0)
            widget = taken.widget()
            if widget is not None:
                widget.deleteLater()
        for idx, change in enumerate(self._amount_changes):
            month_abbr = MONTH_NAMES[change.effective_month][:3]
            text = (
                f"From {month_abbr} {change.effective_year}"
                f"  ->  {change.new_amount}"
            )
            row = QHBoxLayout()
            row.addWidget(QLabel(text))
            row.addStretch(1)
            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(
                lambda _checked=False, i=idx: self._on_remove_amount_change(i)
            )
            row.addWidget(remove_btn)
            row_widget = QWidget()
            row_widget.setLayout(row)
            self.amount_changes_list_layout.addWidget(row_widget)

    def _on_add_amount_change(self) -> None:
        """Validate and append a change to the in-memory list."""
        self.change_warning_label.setVisible(False)
        amount_str = self.change_amount_edit.text().strip()
        if not amount_str:
            return
        qdate = self.change_month_edit.date()
        try:
            change = BillAmountChange(
                effective_year=qdate.year(),
                effective_month=qdate.month(),
                new_amount=Amount.from_pounds(float(amount_str)),
            )
        except (ValueError, InvalidBillAmountChangeError):
            self.change_warning_label.setText("Enter a valid month and amount.")
            self.change_warning_label.setVisible(True)
            return
        # One amount per month: a second entry for a month replaces the first,
        # because two amounts cannot both start in the same month.
        self._amount_changes = [
            c for c in self._amount_changes if c.sort_key != change.sort_key
        ]
        self._amount_changes.append(change)
        self._amount_changes.sort(key=lambda c: c.sort_key)
        self.change_amount_edit.clear()
        self._rebuild_amount_changes_list()

    def _on_remove_amount_change(self, idx: int) -> None:
        if 0 <= idx < len(self._amount_changes):
            self._amount_changes.pop(idx)
            self._rebuild_amount_changes_list()

    def get_amount_changes(self) -> tuple[BillAmountChange, ...]:
        """The scheduled amount changes entered in the dialog."""
        return tuple(self._amount_changes)
