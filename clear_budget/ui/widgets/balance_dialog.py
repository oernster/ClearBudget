"""Dialog for setting bank account balance."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)
from PySide6.QtCore import Qt

from clear_budget.domain.value_objects.amount import Amount


class BalanceDialog(QDialog):
    """Dialog for setting bank account balance."""

    def __init__(self, parent=None, current_balance: Amount | None = None) -> None:
        """Initialize balance dialog."""
        super().__init__(parent)
        self.current_balance = current_balance or Amount(pence=0)
        self.setWindowTitle("Set Bank Balance")
        self.setModal(True)
        self.setGeometry(200, 200, 300, 150)
        self.new_balance: Amount | None = None
        self.init_ui()

    def init_ui(self) -> None:
        """Build dialog layout."""
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Bank Account Balance (£):"))
        self.amount_edit = QLineEdit()
        self.amount_edit.setText(f"{self.current_balance.pounds:.2f}")
        self.amount_edit.setPlaceholderText("0.00")
        layout.addWidget(self.amount_edit)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        ok_btn.clicked.connect(self.on_ok)
        cancel_btn.clicked.connect(self.reject)
        self.amount_edit.returnPressed.connect(self.on_ok)

    def on_ok(self) -> None:
        """Handle OK button press."""
        try:
            amount_str = self.amount_edit.text().strip()
            if amount_str:
                self.new_balance = Amount.from_pounds(float(amount_str))
                self.accept()
        except ValueError:
            pass

    def get_balance(self) -> Amount | None:
        """Get balance that was set (returns None if invalid)."""
        return self.new_balance
