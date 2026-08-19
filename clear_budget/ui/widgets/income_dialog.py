"""Dialog for adding/editing income sources.

Two checkboxes, not one. A single "This month only" box used to carry two
unrelated jobs: whether the entry *is* a one-off; how far *this edit*
reaches. Those are independent axes, so one control could not say which it
meant and had to be greyed out in the case it could not express.

    | Regular income     | One-off
    | ------------------ | -------------------------------
    | change all months  | (a one-off exists in one month,
    | change this month  |  so the column collapses)

`one_off_check` picks the column, `scope_check` picks the row. The scope box
is hidden whenever the column collapses. Nothing is greyed and nothing is
silently ignored: `get_income` reports the identity the box asks for, so the
caller can see a conversion was requested rather than inferring it.
"""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui import label_roles
from clear_budget.ui.utils.format_helpers import MONTH_NAMES


class IncomeDialog(QDialog):
    """Dialog for creating/editing an income source."""

    def __init__(
        self,
        parent=None,
        income: IncomeSource | None = None,
        current_month: YearMonth | None = None,
    ) -> None:
        """Initialize income dialog."""
        super().__init__(parent)
        self.income = income
        self.current_month = current_month or YearMonth.today()
        self.setWindowTitle("Add Income" if income is None else "Edit Income")
        self.setModal(True)
        # Size only, never position: see bill_dialog. A fixed virtual-desktop
        # point pins the dialog to one monitor; sized alone, Qt centres it on
        # its parent.
        self.resize(400, 280)
        self.init_ui()
        if income is not None:
            self.load_income(income)
        self._apply_context()

    @property
    def _month_label(self) -> str:
        """The month this dialog is scoped to, named rather than numbered."""
        return f"{MONTH_NAMES[self.current_month.month]} {self.current_month.year}"

    def init_ui(self) -> None:
        """Build dialog layout."""
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Income Source Name:"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)

        from clear_budget.shared.currency import get_symbol

        layout.addWidget(QLabel(f"Amount ({get_symbol()}):"))
        self.amount_edit = QLineEdit()
        layout.addWidget(self.amount_edit)

        layout.addWidget(QLabel("Due Day (1-31; 0 for no fixed day):"))
        self.due_day_spinbox = QSpinBox()
        self.due_day_spinbox.setMinimum(0)
        self.due_day_spinbox.setMaximum(31)
        self.due_day_spinbox.setValue(0)
        layout.addWidget(self.due_day_spinbox)

        month = self._month_label
        self.one_off_check = QCheckBox(f"This is a one-off, {month} only")
        self.one_off_check.setToolTip(
            f"Ticked, this entry happens in {month} and never again. "
            "Unticked, it is a regular income arriving every month."
        )
        layout.addWidget(self.one_off_check)

        self.scope_check = QCheckBox(f"Apply these changes to {month} only")
        self.scope_check.setToolTip(
            f"Ticked, only {month} changes and every other month keeps its "
            "current figures."
        )
        layout.addWidget(self.scope_check)

        self.status_label = QLabel("")
        self.status_label.setObjectName(label_roles.NOTE)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        self.one_off_check.stateChanged.connect(self._apply_context)
        self.scope_check.stateChanged.connect(self._apply_context)

    def load_income(self, income: IncomeSource) -> None:
        """Load income data into form."""
        self.name_edit.setText(income.name)
        self.amount_edit.setText(f"{income.amount.pounds:.2f}")
        self.due_day_spinbox.setValue(income.day_of_month or 0)
        self.one_off_check.setChecked(income.is_month_only)
        if not income.is_month_only and income.has_month_override:
            self.scope_check.setChecked(True)

    def _apply_context(self) -> None:
        """Show the boxes this context can express; say what will happen.

        The scope box is hidden whenever the entry is a one-off, because a
        one-off already exists in exactly one month: there is no wider reach
        for an edit to have.
        """
        wants_one_off = self.one_off_check.isChecked()
        self.scope_check.setVisible(self.income is not None and not wants_one_off)
        text = self._status_text(wants_one_off, self.scope_check.isChecked())
        self.status_label.setText(text)
        label_roles.set_role(self.status_label, self._status_role(wants_one_off))

    def _is_conversion(self, wants_one_off: bool) -> bool:
        """Whether saving would move this entry between one-off and regular."""
        return self.income is not None and self.income.is_month_only != wants_one_off

    def _status_role(self, wants_one_off: bool) -> str:
        """Conversions change other months, so they are warned, not noted."""
        if self._is_conversion(wants_one_off):
            return label_roles.STRONG_WARN
        return label_roles.NOTE

    def _status_text(self, wants_one_off: bool, scope_only: bool) -> str:
        """Say plainly what OK will do, including what it does to other months.

        Both box states arrive as arguments rather than being read off the
        widgets, so the wording is decidable without a QApplication.
        """
        month = self._month_label
        if self.income is None:
            if wants_one_off:
                return f"Added as a one-off for {month} only."
            return "Added as a regular income, arriving every month."
        if self._is_conversion(wants_one_off):
            if wants_one_off:
                return (
                    f"This will remove '{self.income.name}' from every other "
                    f"month, past and future, leaving it in {month} alone."
                )
            return (
                f"This will become a regular income, arriving every month "
                f"rather than in {month} alone."
            )
        if wants_one_off:
            return f"A one-off entry, in {month} alone."
        if scope_only:
            return f"Changes saved for {month} only. Other months are unchanged."
        return "Changes saved for every month."

    def get_income(self) -> IncomeSource | None:
        """Get income from form (returns None if invalid).

        `is_month_only` is the identity the checkbox ASKS for, which on an edit
        may differ from the entry's current identity. The caller compares the
        two to see whether a conversion was requested.
        """
        try:
            name = self.name_edit.text().strip()
            if not name:
                return None

            amount_str = self.amount_edit.text().strip()
            amount = Amount.from_pounds(float(amount_str))

            due_day = self.due_day_spinbox.value()
            due_day_value = due_day if due_day > 0 else None

            return IncomeSource(
                id=self.income.id if self.income else 0,
                name=name,
                amount=amount,
                is_reliable=True,
                day_of_month=due_day_value,
                active=True,
                is_month_only=self.one_off_check.isChecked(),
            )
        except (ValueError, AttributeError):
            return None
