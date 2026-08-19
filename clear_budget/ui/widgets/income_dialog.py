"""Dialog for adding/editing income sources.

One control, one job. A single "This month only" box used to carry two
unrelated jobs: whether the entry *is* a one-off; how far *this edit*
reaches. Those are independent, so one control could not say which it meant
and was greyed out in the case it could not express at all.

Which controls appear depends on what is being edited. Each is labelled
for the job it actually does there:

* adding: `one_off_check` alone, because nothing else has a meaning yet;
* editing a one-off: `one_off_check`, untickable to make it recurring;
* editing a recurring income: `ends_check` with `end_month_edit`, plus
  `scope_check` for how far this edit reaches.

There is deliberately NO way to turn a recurring income into a one-off. That
direction deletes the source, which removes it from months it really did
arrive in. The app does not rewrite history. An income that stops is
recorded by naming its final month, exactly as a bill is, so the months before
it keep what they had.
"""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
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
        self.resize(400, 320)
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

        # Worded exactly as the bill dialog words its own, because it is the
        # same idea and two phrasings for one concept teach the user twice.
        self.ends_check = QCheckBox("This income ends (set a final month)")
        self.ends_check.setToolTip(
            "For an income that stops: a job ending, a loan finishing. The"
            " income stops after the chosen month; earlier months stay"
            " unchanged."
        )
        layout.addWidget(self.ends_check)
        self.end_month_edit = QDateEdit()
        self.end_month_edit.setCalendarPopup(True)
        self.end_month_edit.setDisplayFormat("MMMM yyyy")
        self.end_month_edit.setDate(
            QDate(self.current_month.year, self.current_month.month, 1)
        )
        layout.addWidget(self.end_month_edit)

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
        self.ends_check.stateChanged.connect(self._apply_context)

    def load_income(self, income: IncomeSource) -> None:
        """Load income data into form."""
        self.name_edit.setText(income.name)
        self.amount_edit.setText(f"{income.amount.pounds:.2f}")
        self.due_day_spinbox.setValue(income.day_of_month or 0)
        self.one_off_check.setChecked(income.is_month_only)
        if not income.is_month_only and income.has_month_override:
            self.scope_check.setChecked(True)
        if income.end_ym is not None:
            self.ends_check.setChecked(True)
            self.end_month_edit.setDate(
                QDate(income.end_ym.year, income.end_ym.month, 1)
            )

    def _apply_context(self) -> None:
        """Show the controls this context can express; say what will happen.

        A one-off already exists in exactly one month, so neither an edit
        scope nor a final month has anything to say about it and both are
        hidden. The one-off box itself is hidden when editing a recurring
        income, because ticking it there would mean demoting; demoting
        deletes months that already happened.
        """
        editing = self.income is not None
        is_one_off = editing and self.income.is_month_only
        wants_one_off = self.one_off_check.isChecked()
        self.one_off_check.setVisible(not editing or is_one_off)
        recurring = editing and not is_one_off and not wants_one_off
        self.scope_check.setVisible(recurring)
        self.ends_check.setVisible(recurring)
        self.end_month_edit.setVisible(recurring and self.ends_check.isChecked())
        text = self._status_text(wants_one_off, self.scope_check.isChecked())
        self.status_label.setText(text)
        label_roles.set_role(self.status_label, self._status_role(wants_one_off))

    def _is_promotion(self, wants_one_off: bool) -> bool:
        """Whether saving would turn this one-off into a recurring income.

        Only this direction can be asked for. The reverse would delete the
        source and so erase months that already happened. The box is not
        offered on a recurring income at all.
        """
        return (
            self.income is not None and self.income.is_month_only and not wants_one_off
        )

    def _status_role(self, wants_one_off: bool) -> str:
        """A promotion changes later months, so it is warned, not noted."""
        if self._is_promotion(wants_one_off):
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
        if self._is_promotion(wants_one_off):
            return (
                f"This will become a regular income, arriving every month "
                f"rather than in {month} alone."
            )
        if wants_one_off:
            return f"A one-off entry, in {month} alone."
        if scope_only:
            return f"Changes saved for {month} only. Other months are unchanged."
        return "Changes saved for every month."

    def _chosen_end_month(self) -> YearMonth | None:
        """The final month the user named; None when the income continues.

        An existing start month is carried through untouched: it records when
        the income began and no edit here is a claim about that.
        """
        if not self.ends_check.isChecked():
            return None
        chosen = self.end_month_edit.date()
        return YearMonth(year=chosen.year(), month=chosen.month())

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
                start_ym=self.income.start_ym if self.income else None,
                end_ym=self._chosen_end_month(),
                is_month_only=self.one_off_check.isChecked(),
            )
        except (ValueError, AttributeError):
            return None
