"""Dialog for adding/editing bills."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QPushButton,
)
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


class BillDialog(QDialog):
    """Dialog for creating/editing a bill."""

    CATEGORIES = [
        "housing",
        "utilities",
        "subscriptions",
        "credit_payment",
        "groceries",
        "discretionary",
        "one_time",
    ]

    @staticmethod
    def _display_category(internal_name: str) -> str:
        """Convert internal category name to display format (title case)."""
        return internal_name.replace("_", " ").title()

    @staticmethod
    def _internal_category(display_name: str) -> str:
        """Convert display category name to internal format (lowercase, underscores)."""
        return display_name.lower().replace(" ", "_")

    BILL_TYPES = ["fixed", "variable", "expiring"]

    def __init__(
        self,
        parent=None,
        bill: Bill | None = None,
        payment_method_repo=None,
        current_month: YearMonth | None = None,
    ) -> None:
        """Initialize bill dialog."""
        super().__init__(parent)
        self.bill = bill
        self.payment_method_repo = payment_method_repo
        self.current_month = current_month or YearMonth.today()
        self.setWindowTitle("Add Bill" if bill is None else "Edit Bill")
        self.setModal(True)
        self.setGeometry(100, 100, 400, 300)
        self.init_ui()
        if bill is not None:
            self.load_bill(bill)
        else:
            self.month_only_check.setEnabled(False)

    def init_ui(self) -> None:
        """Build dialog layout."""
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Bill Name:"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)

        from clear_budget.shared.currency import get_symbol

        layout.addWidget(QLabel(f"Amount ({get_symbol()}):"))
        self.amount_edit = QLineEdit()
        layout.addWidget(self.amount_edit)

        layout.addWidget(QLabel("Payment Method:"))
        self.payment_method_combo = QComboBox()
        self._populate_payment_methods()
        layout.addWidget(self.payment_method_combo)

        layout.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        display_categories = [self._display_category(cat) for cat in self.CATEGORIES]
        self.category_combo.addItems(display_categories)
        layout.addWidget(self.category_combo)

        layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(self.BILL_TYPES)
        layout.addWidget(self.type_combo)

        layout.addWidget(QLabel("Day of Month (0 = N/A):"))
        self.day_spin = QSpinBox()
        self.day_spin.setMinimum(0)
        self.day_spin.setMaximum(31)
        self.day_spin.setValue(0)
        layout.addWidget(self.day_spin)

        self.pays_card_label = QLabel("Pays Card:")
        layout.addWidget(self.pays_card_label)
        self.pays_card_combo = QComboBox()
        self.pays_card_combo.addItem("(none)", None)
        if self.payment_method_repo:
            for card in self.payment_method_repo.get_all_credit_cards(
                include_inactive=False
            ):
                self.pays_card_combo.addItem(card.name, card.id)
        layout.addWidget(self.pays_card_combo)

        self.month_only_check = QCheckBox("This month only")
        self.month_only_check.setToolTip(
            "Override amount/date for this month; other months unchanged"
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
        self.category_combo.currentTextChanged.connect(
            lambda _: self._update_pays_card_visibility()
        )
        self._update_pays_card_visibility()

    def _on_month_only_changed(self) -> None:
        if self.month_only_check.isChecked():
            month_str = f"{self.current_month.month}/{self.current_month.year}"
            self.month_only_status.setText(
                f"Changes saved for {month_str} only - template unchanged"
            )
        else:
            self.month_only_status.setText("")

    def _update_pays_card_visibility(self) -> None:
        visible = (
            self._internal_category(self.category_combo.currentText())
            == "credit_payment"
        )
        self.pays_card_label.setVisible(visible)
        self.pays_card_combo.setVisible(visible)

    def _populate_payment_methods(self) -> None:
        self.payment_method_combo.clear()
        self.payment_method_combo.addItem("Bank Account")
        self.payment_method_combo.setItemData(0, 1)
        if self.payment_method_repo:
            for i, card in enumerate(
                self.payment_method_repo.get_all_credit_cards(), start=1
            ):
                self.payment_method_combo.addItem(card.name)
                self.payment_method_combo.setItemData(i, card.id)

    def load_bill(self, bill: Bill) -> None:
        """Load bill data into form."""
        self.name_edit.setText(bill.name)
        self.amount_edit.setText(f"{bill.amount.pounds:.2f}")

        # Find payment method by ID
        for i in range(self.payment_method_combo.count()):
            if self.payment_method_combo.itemData(i) == bill.payment_method_id:
                self.payment_method_combo.setCurrentIndex(i)
                break

        self.category_combo.setCurrentText(self._display_category(bill.category))
        self.type_combo.setCurrentText(bill.bill_type)
        if bill.day_of_month:
            self.day_spin.setValue(bill.day_of_month)
        if bill.target_card_id is not None:
            for i in range(self.pays_card_combo.count()):
                if self.pays_card_combo.itemData(i) == bill.target_card_id:
                    self.pays_card_combo.setCurrentIndex(i)
                    break
        self._update_pays_card_visibility()
        if bill.has_month_override:
            self.month_only_check.setChecked(True)

    def get_bill(self) -> Bill | None:
        """Get bill from form (returns None if invalid)."""
        try:
            name = self.name_edit.text().strip()
            if not name:
                return None

            amount_str = self.amount_edit.text().strip()
            amount = Amount.from_pounds(float(amount_str))

            # Convert display category back to internal format
            display_category = self.category_combo.currentText()
            category = self._internal_category(display_category)
            bill_type = self.type_combo.currentText()
            day = self.day_spin.value() if self.day_spin.value() > 0 else None

            # Payment method ID
            selected_text = self.payment_method_combo.currentText()
            if selected_text == "Bank Account":
                payment_method_id = 1
            else:
                payment_method_id = self.payment_method_combo.currentData()
                if payment_method_id is None and self.payment_method_repo:
                    cards = self.payment_method_repo.get_all_credit_cards()
                    match = next((c for c in cards if c.name == selected_text), None)
                    payment_method_id = match.id if match else 1

            target_card_id = self.pays_card_combo.currentData()

            return Bill(
                id=self.bill.id if self.bill else 0,
                name=name,
                amount=amount,
                payment_method_id=payment_method_id,
                category=category,
                bill_type=bill_type,
                day_of_month=day,
                start_ym=self.bill.start_ym if self.bill else YearMonth(2000, 1),
                end_ym=self.bill.end_ym if self.bill else None,
                active=True,
                target_card_id=target_card_id,
            )
        except (ValueError, AttributeError):
            return None
