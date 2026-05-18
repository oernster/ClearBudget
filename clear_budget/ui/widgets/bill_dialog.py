"""Dialog for adding/editing bills."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QPushButton,
)
from PySide6.QtCore import Qt

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
        """Convert internal category name to display format (title case, no underscores)."""
        return internal_name.replace("_", " ").title()

    @staticmethod
    def _internal_category(display_name: str) -> str:
        """Convert display category name to internal format (lowercase, underscores)."""
        return display_name.lower().replace(" ", "_")
    BILL_TYPES = ["fixed", "variable", "expiring"]

    def __init__(self, parent=None, bill: Bill | None = None, payment_method_repo=None, current_month: YearMonth | None = None) -> None:
        """Initialize bill dialog."""
        super().__init__(parent)
        self.bill = bill
        self.payment_method_repo = payment_method_repo
        self.current_month = current_month or YearMonth(2026, 1)
        self.setWindowTitle("Add Bill" if bill is None else "Edit Bill")
        self.setModal(True)
        self.setGeometry(100, 100, 400, 300)
        self.init_ui()
        if bill is not None:
            self.load_bill(bill)

    def init_ui(self) -> None:
        """Build dialog layout."""
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Bill Name:"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Amount (£):"))
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

        layout.addWidget(QLabel("Day of Month (leave blank for N/A):"))
        self.day_spin = QSpinBox()
        self.day_spin.setMinimum(0)
        self.day_spin.setMaximum(31)
        self.day_spin.setValue(0)
        layout.addWidget(self.day_spin)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

    def _populate_payment_methods(self) -> None:
        """Populate payment method dropdown from database."""
        print("[DIALOG] _populate_payment_methods() called")
        self.payment_method_combo.clear()
        self.payment_method_combo.addItem("Bank Account")
        self.payment_method_combo.setItemData(0, 1)
        print(f"[DIALOG] Added 'Bank Account' at index 0 with data=1")

        if self.payment_method_repo:
            print(f"[DIALOG] payment_method_repo exists, fetching cards...")
            cards = self.payment_method_repo.get_all_credit_cards()
            print(f"[DIALOG] Found {len(cards)} credit cards")
            for i, card in enumerate(cards, start=1):
                self.payment_method_combo.addItem(card.name)
                self.payment_method_combo.setItemData(i, card.id)
                print(f"[DIALOG] Added '{card.name}' at index {i} with data={card.id}")
        else:
            print(f"[DIALOG] payment_method_repo is None!")

        print(f"[DIALOG] Final combo count: {self.payment_method_combo.count()}")
        for idx in range(self.payment_method_combo.count()):
            text = self.payment_method_combo.itemText(idx)
            data = self.payment_method_combo.itemData(idx)
            print(f"[DIALOG]   Index {idx}: text='{text}', data={data}")

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

            # Get payment method ID from combo box
            selected_text = self.payment_method_combo.currentText()
            print(f"\n[GET_BILL] ===== PAYMENT METHOD LOGIC =====")
            print(f"[GET_BILL] Selected text from combo: '{selected_text}'")
            print(f"[GET_BILL] Current index: {self.payment_method_combo.currentIndex()}")

            # Direct match: check if it's the bank account
            if selected_text == "Bank Account":
                payment_method_id = 1
                print(f"[GET_BILL] Matched 'Bank Account' -> payment_method_id=1")
            else:
                # Search for matching card by name
                payment_method_id = None
                print(f"[GET_BILL] Not Bank Account, searching for card '{selected_text}'")
                if self.payment_method_repo:
                    cards = self.payment_method_repo.get_all_credit_cards()
                    print(f"[GET_BILL] Fetched {len(cards)} cards from repo")
                    for card in cards:
                        print(f"[GET_BILL]   Checking card: name='{card.name}', id={card.id}")
                        if card.name == selected_text:
                            payment_method_id = card.id
                            print(f"[GET_BILL] MATCH FOUND: '{card.name}' -> payment_method_id={card.id}")
                            break
                else:
                    print(f"[GET_BILL] payment_method_repo is None!")

                # Fallback: try userData
                if payment_method_id is None:
                    data = self.payment_method_combo.currentData()
                    print(f"[GET_BILL] No card name match, trying userData: {data}")
                    payment_method_id = data

                # Final fallback: default to bank if still None
                if payment_method_id is None:
                    print(f"[GET_BILL] No match and no userData, defaulting to Bank (1)")
                    payment_method_id = 1
                else:
                    print(f"[GET_BILL] Final payment_method_id={payment_method_id}")

            print(f"[GET_BILL] ===== END PAYMENT METHOD =====\n")

            return Bill(
                id=self.bill.id if self.bill else 0,
                name=name,
                amount=amount,
                payment_method_id=payment_method_id,
                category=category,
                bill_type=bill_type,
                day_of_month=day,
                start_ym=self.bill.start_ym if self.bill else self.current_month,
                end_ym=self.bill.end_ym if self.bill else None,
                active=True,
            )
        except (ValueError, AttributeError):
            return None
