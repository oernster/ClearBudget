"""Dialog for setting bank account balance."""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from clear_budget.ui.utils.amount_fields import (
    AmountFieldRefused,
    AmountRefusalMixin,
    field_pence,
)

_LABEL = "Bank balance"


class BalanceDialog(AmountRefusalMixin, QDialog):
    """Dialog for setting bank account balance."""

    def __init__(self, parent=None, current_balance_pence: int = 0) -> None:
        """Initialize balance dialog.

        The current balance arrives as signed pence because an overdrawn
        account stores a negative one, which an Amount cannot hold.
        """
        super().__init__(parent)
        self.current_balance_pence = current_balance_pence
        self.setWindowTitle("Set Bank Balance")
        self.setModal(True)
        self.resize(300, 150)
        self.new_balance_pence: int | None = None
        self.init_ui()

    def init_ui(self) -> None:
        """Build dialog layout."""
        layout = QVBoxLayout()

        from clear_budget.shared.currency import get_symbol

        layout.addWidget(QLabel(f"Bank Account Balance ({get_symbol()}):"))
        self.amount_edit = QLineEdit()
        self.amount_edit.setText(f"{self.current_balance_pence / 100:.2f}")
        self.amount_edit.setPlaceholderText("0.00")
        # Pre-select the current balance so typing replaces it outright.
        self.amount_edit.selectAll()
        self.amount_edit.setFocus()
        layout.addWidget(self.amount_edit)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        # Named the default rather than left as the first autoDefault
        # button in the row: reordering the row would otherwise put Return
        # on Cancel.
        ok_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setAutoDefault(False)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        ok_btn.clicked.connect(self.on_ok)
        cancel_btn.clicked.connect(self.reject)
        # No returnPressed connection: OK is the default button and a
        # QLineEdit ignores Return so that it reaches OK. Both would run
        # on_ok twice on one press.

    def on_ok(self) -> None:
        """Save the balance exactly as typed; otherwise say why and stay open.

        Signed: an overdrawn account is negative. This dialog pre-fills the
        balance as it stands, so a negative figure must be accepted back.
        """
        try:
            pence = field_pence(self.amount_edit, label=_LABEL, signed=True)
        except AmountFieldRefused as refusal:
            self._refuse_amount(refusal.field, refusal)
            return
        self.new_balance_pence = pence
        self.accept()

    def get_balance_pence(self) -> int | None:
        """The balance set, in signed pence; None if the dialog was cancelled."""
        return self.new_balance_pence
