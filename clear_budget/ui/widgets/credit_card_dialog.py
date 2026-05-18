"""Dialog for adding/editing credit cards."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QPushButton,
)
from PySide6.QtCore import Qt

from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount


class CreditCardDialog(QDialog):
    """Dialog for creating/editing a credit card."""

    def __init__(self, parent=None, card: CreditCard | None = None) -> None:
        """Initialize credit card dialog."""
        super().__init__(parent)
        self.card = card
        self.setWindowTitle("Add Credit Card" if card is None else "Edit Credit Card")
        self.setModal(True)
        self.setGeometry(100, 100, 450, 400)
        self.init_ui()
        if card is not None:
            self.load_card(card)

    def init_ui(self) -> None:
        """Build dialog layout."""
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Card Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., CapitalOne, Vanquis, Jaja")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Credit Limit (£):"))
        self.limit_edit = QLineEdit()
        layout.addWidget(self.limit_edit)

        layout.addWidget(QLabel("Current Balance (£):"))
        self.balance_edit = QLineEdit()
        self.balance_edit.setText("0.00")
        layout.addWidget(self.balance_edit)

        layout.addWidget(QLabel("Interest Rate (% APR):"))
        self.interest_spin = QDoubleSpinBox()
        self.interest_spin.setMinimum(0.0)
        self.interest_spin.setMaximum(100.0)
        self.interest_spin.setSingleStep(0.1)
        self.interest_spin.setValue(0.0)
        layout.addWidget(self.interest_spin)

        layout.addWidget(QLabel("Payment Due Day (1-31):"))
        self.due_day_spin = QSpinBox()
        self.due_day_spin.setMinimum(1)
        self.due_day_spin.setMaximum(31)
        self.due_day_spin.setValue(1)
        layout.addWidget(self.due_day_spin)

        # Expiry date layout
        expiry_layout = QHBoxLayout()
        expiry_layout.addWidget(QLabel("Card Expiry:"))
        expiry_layout.addWidget(QLabel("Month (1-12):"))
        self.expiry_month_spin = QSpinBox()
        self.expiry_month_spin.setMinimum(1)
        self.expiry_month_spin.setMaximum(12)
        self.expiry_month_spin.setValue(1)
        expiry_layout.addWidget(self.expiry_month_spin)
        expiry_layout.addWidget(QLabel("Year:"))
        self.expiry_year_spin = QSpinBox()
        self.expiry_year_spin.setMinimum(2026)
        self.expiry_year_spin.setMaximum(2050)
        self.expiry_year_spin.setValue(2030)
        expiry_layout.addWidget(self.expiry_year_spin)
        layout.addLayout(expiry_layout)

        layout.addWidget(QLabel("Minimum Payment (£) [optional]:"))
        self.min_payment_edit = QLineEdit()
        layout.addWidget(self.min_payment_edit)

        self.active_checkbox = QCheckBox("Active")
        self.active_checkbox.setChecked(True)
        layout.addWidget(self.active_checkbox)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

    def load_card(self, card: CreditCard) -> None:
        """Load card data into form."""
        self.name_edit.setText(card.name)
        self.limit_edit.setText(f"{card.credit_limit.pounds:.2f}")
        self.balance_edit.setText(f"{card.current_balance_used.pounds:.2f}")
        if card.interest_rate_apr is not None:
            self.interest_spin.setValue(card.interest_rate_apr)
        self.due_day_spin.setValue(card.payment_due_day)
        if card.card_expiry_month is not None:
            self.expiry_month_spin.setValue(card.card_expiry_month)
        if card.card_expiry_year is not None:
            self.expiry_year_spin.setValue(card.card_expiry_year)
        if card.minimum_payment_pence is not None:
            min_pmt_pounds = card.minimum_payment_pence / 100
            self.min_payment_edit.setText(f"{min_pmt_pounds:.2f}")
        self.active_checkbox.setChecked(card.active == 1)

    def get_card(self) -> CreditCard | None:
        """Get card from form (returns None if invalid)."""
        try:
            name = self.name_edit.text().strip()
            if not name:
                return None

            limit_str = self.limit_edit.text().strip()
            if not limit_str:
                return None
            limit = Amount.from_pounds(float(limit_str))

            balance_str = self.balance_edit.text().strip()
            balance = Amount.from_pounds(float(balance_str)) if balance_str else Amount(pence=0)

            interest_rate = (
                self.interest_spin.value() if self.interest_spin.value() > 0 else None
            )

            due_day = self.due_day_spin.value()

            expiry_month = self.expiry_month_spin.value() if self.expiry_month_spin.value() > 0 else None
            expiry_year = self.expiry_year_spin.value() if self.expiry_month_spin.value() > 0 else None

            min_pmt_str = self.min_payment_edit.text().strip()
            min_pmt_pence = None
            if min_pmt_str:
                min_pmt_pence = int(float(min_pmt_str) * 100)

            active = 1 if self.active_checkbox.isChecked() else 0

            return CreditCard(
                id=self.card.id if self.card else 0,
                name=name,
                credit_limit=limit,
                current_balance_used=balance,
                interest_rate_apr=interest_rate,
                payment_due_day=due_day,
                card_expiry_month=expiry_month,
                card_expiry_year=expiry_year,
                minimum_payment_pence=min_pmt_pence,
                active=active,
            )
        except (ValueError, AttributeError, TypeError):
            return None
