"""Dialog for adding/editing credit cards."""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QDateEdit,
    QCheckBox,
    QPushButton,
    QWidget,
)
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.credit_limit_change import CreditLimitChange
from clear_budget.shared.errors import InvalidCreditLimitChangeError
from clear_budget.ui.utils.format_helpers import MONTH_NAMES

_MAX_SCHEDULE_YEAR = 2050
_LIMIT_FIELD_MIN_WIDTH_PX = 120


class CreditCardDialog(QDialog):
    """Dialog for creating/editing a credit card."""

    def __init__(self, parent=None, card: CreditCard | None = None) -> None:
        """Initialize credit card dialog."""
        super().__init__(parent)
        self.card = card
        self._limit_changes: list[CreditLimitChange] = []
        self.setWindowTitle("Add Credit Card" if card is None else "Edit Credit Card")
        self.setModal(True)
        # Size only (no fixed position) so the modal centres on its parent.
        self.resize(560, 660)
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

        from clear_budget.shared.currency import get_symbol

        _sym = get_symbol()
        layout.addWidget(QLabel(f"Credit Limit ({_sym}):"))
        self.limit_edit = QLineEdit()
        self.limit_edit.setMinimumWidth(_LIMIT_FIELD_MIN_WIDTH_PX)
        layout.addWidget(self.limit_edit)

        layout.addWidget(QLabel(f"Current Balance ({_sym}):"))
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
        self.has_expiry_checkbox = QCheckBox("Card has expiry date")
        self.has_expiry_checkbox.setChecked(False)
        layout.addWidget(self.has_expiry_checkbox)

        expiry_layout = QHBoxLayout()
        expiry_layout.addWidget(QLabel("  Month (1-12):"))
        self.expiry_month_spin = QSpinBox()
        self.expiry_month_spin.setMinimum(1)
        self.expiry_month_spin.setMaximum(12)
        self.expiry_month_spin.setValue(1)
        self.expiry_month_spin.setEnabled(False)
        expiry_layout.addWidget(self.expiry_month_spin)
        expiry_layout.addWidget(QLabel("Year:"))
        self.expiry_year_spin = QSpinBox()
        self.expiry_year_spin.setMinimum(2026)
        self.expiry_year_spin.setMaximum(2050)
        self.expiry_year_spin.setValue(2030)
        self.expiry_year_spin.setEnabled(False)
        expiry_layout.addWidget(self.expiry_year_spin)
        layout.addLayout(expiry_layout)

        self.has_expiry_checkbox.toggled.connect(self.expiry_month_spin.setEnabled)
        self.has_expiry_checkbox.toggled.connect(self.expiry_year_spin.setEnabled)

        layout.addWidget(QLabel("Minimum Payment [optional, overridden by % below]:"))
        min_pmt_row = QHBoxLayout()
        min_pmt_row.addWidget(QLabel(_sym))
        self.min_payment_edit = QLineEdit()
        min_pmt_row.addWidget(self.min_payment_edit)
        layout.addLayout(min_pmt_row)

        layout.addWidget(
            QLabel(
                f"Min Payment % of balance [optional, e.g. 4.43 - overrides fixed {_sym}]:"
            )
        )
        self.min_pct_spin = QDoubleSpinBox()
        self.min_pct_spin.setMinimum(0.0)
        self.min_pct_spin.setMaximum(100.0)
        self.min_pct_spin.setSingleStep(0.01)
        self.min_pct_spin.setDecimals(2)
        self.min_pct_spin.setValue(0.0)
        self.min_pct_spin.setSuffix(" %")
        layout.addWidget(self.min_pct_spin)

        self.active_checkbox = QCheckBox("Active")
        self.active_checkbox.setChecked(True)
        layout.addWidget(self.active_checkbox)

        layout.addWidget(QLabel("Scheduled limit changes [optional]:"))
        self.changes_container = QWidget()
        self.changes_list_layout = QVBoxLayout(self.changes_container)
        self.changes_list_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.changes_container)

        add_change_row = QHBoxLayout()
        add_change_row.addWidget(QLabel("Effective:"))
        self.change_date_edit = QDateEdit()
        self.change_date_edit.setCalendarPopup(True)
        self.change_date_edit.setDisplayFormat("dd MMM yyyy")
        self.change_date_edit.setMinimumDate(QDate.currentDate())
        self.change_date_edit.setMaximumDate(QDate(_MAX_SCHEDULE_YEAR, 12, 31))
        self.change_date_edit.setDate(QDate.currentDate())
        add_change_row.addWidget(self.change_date_edit)
        add_change_row.addWidget(QLabel(f"New limit ({_sym}):"))
        self.change_limit_edit = QLineEdit()
        self.change_limit_edit.setMinimumWidth(_LIMIT_FIELD_MIN_WIDTH_PX)
        add_change_row.addWidget(self.change_limit_edit)
        add_change_btn = QPushButton("Add change")
        add_change_btn.clicked.connect(self._on_add_change)
        add_change_row.addWidget(add_change_btn)
        layout.addLayout(add_change_row)

        self.change_warning_label = QLabel("")
        self.change_warning_label.setStyleSheet("color: #f59e0b; font-size: 12px;")
        self.change_warning_label.setWordWrap(True)
        self.change_warning_label.setVisible(False)
        layout.addWidget(self.change_warning_label)
        self._rebuild_changes_list()

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
        has_expiry = (
            card.card_expiry_month is not None and card.card_expiry_year is not None
        )
        self.has_expiry_checkbox.setChecked(has_expiry)
        if has_expiry:
            self.expiry_month_spin.setValue(card.card_expiry_month)
            self.expiry_year_spin.setValue(card.card_expiry_year)
        if card.minimum_payment_pence is not None:
            self.min_payment_edit.setText(f"{card.minimum_payment_pence / 100:.2f}")
        if card.minimum_payment_percent is not None:
            self.min_pct_spin.setValue(card.minimum_payment_percent)
        self.active_checkbox.setChecked(card.active == 1)
        self._limit_changes = list(card.scheduled_limit_changes)
        self._rebuild_changes_list()

    def _rebuild_changes_list(self) -> None:
        """Redraw the scheduled-changes list from the in-memory model."""
        while self.changes_list_layout.count():
            taken = self.changes_list_layout.takeAt(0)
            widget = taken.widget()
            if widget is not None:
                widget.deleteLater()
        for idx, change in enumerate(self._limit_changes):
            month_abbr = MONTH_NAMES[change.effective_month][:3]
            text = (
                f"{change.effective_day} {month_abbr} {change.effective_year}"
                f"  →  {change.new_limit}"
            )
            row = QHBoxLayout()
            row.addWidget(QLabel(text))
            row.addStretch(1)
            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(
                lambda _checked=False, i=idx: self._on_remove_change(i)
            )
            row.addWidget(remove_btn)
            row_widget = QWidget()
            row_widget.setLayout(row)
            self.changes_list_layout.addWidget(row_widget)

    def _show_change_warning(self, text: str) -> None:
        self.change_warning_label.setText(text)
        self.change_warning_label.setVisible(True)

    def _on_add_change(self) -> None:
        """Validate and append a scheduled change to the in-memory list."""
        self.change_warning_label.setVisible(False)
        limit_str = self.change_limit_edit.text().strip()
        if not limit_str:
            return
        qdate = self.change_date_edit.date()
        try:
            new_limit = Amount.from_pounds(float(limit_str))
            change = CreditLimitChange(
                effective_year=qdate.year(),
                effective_month=qdate.month(),
                effective_day=qdate.day(),
                new_limit=new_limit,
            )
        except (ValueError, InvalidCreditLimitChangeError):
            self._show_change_warning("Enter a valid date and limit.")
            return
        self._limit_changes.append(change)
        self._limit_changes.sort(key=lambda c: c.sort_key)
        self.change_limit_edit.clear()
        self._rebuild_changes_list()
        self._warn_if_below_balance(new_limit)

    def _warn_if_below_balance(self, new_limit: Amount) -> None:
        """Flag a change that would drop the limit below the current balance."""
        try:
            used = Amount.from_pounds(float(self.balance_edit.text().strip() or "0"))
        except ValueError:
            return
        if new_limit.pence < used.pence:
            self._show_change_warning(
                f"That limit ({new_limit}) is below the current balance "
                f"({used}); the card would be over its limit."
            )

    def _on_remove_change(self, idx: int) -> None:
        if 0 <= idx < len(self._limit_changes):
            self._limit_changes.pop(idx)
            self._rebuild_changes_list()

    def get_limit_changes(self) -> tuple[CreditLimitChange, ...]:
        """Return the scheduled limit changes entered in the dialog."""
        return tuple(self._limit_changes)

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
            balance = (
                Amount.from_pounds(float(balance_str))
                if balance_str
                else Amount(pence=0)
            )

            interest_rate = (
                self.interest_spin.value() if self.interest_spin.value() > 0 else None
            )

            due_day = self.due_day_spin.value()

            if self.has_expiry_checkbox.isChecked():
                expiry_month = self.expiry_month_spin.value()
                expiry_year = self.expiry_year_spin.value()
            else:
                expiry_month = None
                expiry_year = None

            min_pmt_str = self.min_payment_edit.text().strip()
            min_pmt_pence = None
            if min_pmt_str:
                min_pmt_pence = Amount.from_pounds(float(min_pmt_str)).pence

            active = 1 if self.active_checkbox.isChecked() else 0

            min_pct = (
                self.min_pct_spin.value() if self.min_pct_spin.value() > 0 else None
            )

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
                minimum_payment_percent=min_pct,
                active=active,
            )
        except (ValueError, AttributeError, TypeError):
            return None
