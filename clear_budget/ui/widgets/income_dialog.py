"""Dialog for adding/editing income sources."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount


class IncomeDialog(QDialog):
    """Dialog for creating/editing an income source."""

    def __init__(self, parent=None, income: IncomeSource | None = None) -> None:
        """Initialize income dialog."""
        super().__init__(parent)
        self.income = income
        self.setWindowTitle("Add Income" if income is None else "Edit Income")
        self.setModal(True)
        self.setGeometry(100, 100, 400, 220)
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

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

    def load_income(self, income: IncomeSource) -> None:
        """Load income data into form."""
        self.name_edit.setText(income.name)
        self.amount_edit.setText(f"{income.amount.pounds:.2f}")
        self.due_day_spinbox.setValue(income.day_of_month or 0)

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

            return IncomeSource(
                id=self.income.id if self.income else 0,
                name=name,
                amount=amount,
                is_reliable=True,
                day_of_month=due_day_value,
                active=True,
            )
        except (ValueError, AttributeError):
            return None
