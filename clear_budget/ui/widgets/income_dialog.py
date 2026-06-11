"""Dialog for adding/editing income sources."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QCheckBox,
)

from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


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
        self.setGeometry(100, 100, 400, 240)
        self.init_ui()
        if income is not None:
            self.load_income(income)

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

        layout.addWidget(QLabel("Due Day (1-31, or 0 for no fixed day):"))
        self.due_day_spinbox = QSpinBox()
        self.due_day_spinbox.setMinimum(0)
        self.due_day_spinbox.setMaximum(31)
        self.due_day_spinbox.setValue(0)
        layout.addWidget(self.due_day_spinbox)

        self.month_only_check = QCheckBox("This month only")
        self.month_only_check.setToolTip(
            "Add as a one-off entry for this month only - not a recurring source"
        )
        layout.addWidget(self.month_only_check)

        self.month_only_status = QLabel("")
        self.month_only_status.setStyleSheet(
            "color: #60a5fa; font-size: 11px; padding: 2px;"
        )
        layout.addWidget(self.month_only_status)
        self.month_only_check.stateChanged.connect(self._on_month_only_changed)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

    def _on_month_only_changed(self) -> None:
        if self.month_only_check.isChecked():
            month_str = f"{self.current_month.month}/{self.current_month.year}"
            if self.income is not None and not self.income.is_month_only:
                self.month_only_status.setText(
                    f"Changes saved for {month_str} only - template unchanged"
                )
            else:
                self.month_only_status.setText(
                    f"Added as a one-off for {month_str} only"
                )
        else:
            self.month_only_status.setText("")

    def load_income(self, income: IncomeSource) -> None:
        """Load income data into form."""
        self.name_edit.setText(income.name)
        self.amount_edit.setText(f"{income.amount.pounds:.2f}")
        self.due_day_spinbox.setValue(income.day_of_month or 0)
        if income.is_month_only:
            self.month_only_check.setChecked(True)
            self.month_only_check.setEnabled(False)
        else:
            self.month_only_check.setToolTip(
                "Override amount/date for this month; other months unchanged"
            )
            if income.has_month_override:
                self.month_only_check.setChecked(True)

    def get_income(self) -> IncomeSource | None:
        """Get income from form (returns None if invalid)."""
        try:
            name = self.name_edit.text().strip()
            if not name:
                return None

            amount_str = self.amount_edit.text().strip()
            amount = Amount.from_pounds(float(amount_str))

            due_day = self.due_day_spinbox.value()
            due_day_value = due_day if due_day > 0 else None

            is_month_only = (
                self.income.is_month_only
                if self.income
                else self.month_only_check.isChecked()
            )

            return IncomeSource(
                id=self.income.id if self.income else 0,
                name=name,
                amount=amount,
                is_reliable=True,
                day_of_month=due_day_value,
                active=True,
                is_month_only=is_month_only,
            )
        except (ValueError, AttributeError):
            return None
