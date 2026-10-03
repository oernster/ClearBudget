"""BankAccountSettingsDialog - overdraft, Safe to Spend and currency.

The display-currency picker lived in its own Preferences dialog behind a
cog button; both folded in here because one small dialog per setting was
clutter the tray paid for. The bank button now opens everything the
account can configure.
"""

from decimal import Decimal, InvalidOperation, localcontext

from PySide6.QtWidgets import (
    QSpinBox,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.shared.currency import CURRENCIES, get_symbol
from clear_budget.shared.errors import InvalidRateError
from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui.utils.amount_fields import (
    AmountFieldRefused,
    AmountRefusalMixin,
    field_pence,
)
from clear_budget.ui.widgets.themed_combo_box import ThemedComboBox

_RATE_PLACES = 2
_BASIS_POINTS_PER_PERCENT = 10**_RATE_PLACES
# Far above any rate the overdraft projection is meant for. It exists so a
# typing slip cannot store a figure the settings table could not hold.
_MAX_APR_PERCENT = 1000
_LIMIT_LABEL = "Overdraft limit"
_FLOOR_LABEL = "Buffer"
_APR_REFUSAL = (
    f"Overdraft APR: enter a rate from 0 to {_MAX_APR_PERCENT}%,"
    f" to at most {_RATE_PLACES} decimal places."
)


def apr_basis_points_from_text(text: str) -> int:
    """A typed APR percentage as exact basis points; empty means none (0).

    Read as a decimal, never a float: `nan` and `inf` used to raise out of
    the Save handler. Raises InvalidRateError for anything that is not a
    finite rate from 0 to _MAX_APR_PERCENT in whole basis points.
    """
    cleaned = text.strip().removesuffix("%").strip()
    if not cleaned:
        return 0
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise InvalidRateError(_APR_REFUSAL) from None
    if not value.is_finite() or value.is_signed() or value > _MAX_APR_PERCENT:
        raise InvalidRateError(_APR_REFUSAL)
    with localcontext() as exact:
        # Enough digits that scaling can never round a trailing digit away.
        exact.prec = len(value.as_tuple().digits) + _RATE_PLACES + 1
        scaled = value.scaleb(_RATE_PLACES)
    if scaled != scaled.to_integral_value():
        raise InvalidRateError(_APR_REFUSAL)
    return int(scaled)


# Bounds on how far ahead a spendable figure must hold.
_MIN_WINDOW_MONTHS = 1
_MAX_WINDOW_MONTHS = 12


class BankAccountSettingsDialog(AmountRefusalMixin, QDialog):
    """Dialog for configuring the bank account's overdraft facility."""

    def __init__(
        self,
        parent=None,
        *,
        overdraft_limit: Amount | None = None,
        overdraft_apr_basis_points: int = 0,
        safe_to_spend_floor: Amount | None = None,
        sustainable_window_months: int = 4,
        currency_code: str = "GBP",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bank Account Settings")
        self.setMinimumWidth(ui_scale.px(420))
        self._overdraft_limit = overdraft_limit or Amount(pence=0)
        self._overdraft_apr_basis_points = overdraft_apr_basis_points
        self._safe_to_spend_floor = safe_to_spend_floor or Amount(pence=0)
        self._sustainable_window_months = sustainable_window_months
        self._currency_code = currency_code
        self._new_overdraft_limit: Amount | None = None
        self._new_overdraft_apr_basis_points: int | None = None
        self._new_safe_to_spend_floor: Amount | None = None
        self._new_sustainable_window_months: int | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(ui_scale.px(10))
        layout.setContentsMargins(
            ui_scale.px(24), ui_scale.px(20), ui_scale.px(24), ui_scale.px(20)
        )

        title = QLabel("Overdraft Facility")
        title.setStyleSheet(ui_scale.style("font-size: 16px; font-weight: bold;"))
        layout.addWidget(title)

        info = QLabel(
            "Used to judge whether a mid-month dip below zero is covered"
            " by an agreed facility."
        )
        info.setWordWrap(True)
        info.setObjectName(label_roles.SUBTLE)
        layout.addWidget(info)

        self._has_overdraft_check = QCheckBox("I have an overdraft facility")
        self._has_overdraft_check.setChecked(self._overdraft_limit.pence > 0)
        self._has_overdraft_check.toggled.connect(self._on_toggled)
        layout.addWidget(self._has_overdraft_check)

        layout.addWidget(QLabel(f"Overdraft limit ({get_symbol()}):"))
        self._limit_edit = QLineEdit()
        self._limit_edit.setText(f"{self._overdraft_limit.pounds:.2f}")
        self._limit_edit.setPlaceholderText("0.00")
        layout.addWidget(self._limit_edit)

        layout.addWidget(QLabel("Overdraft APR (%):"))
        self._apr_edit = QLineEdit()
        self._apr_edit.setText(
            f"{self._overdraft_apr_basis_points / _BASIS_POINTS_PER_PERCENT:.2f}"
        )
        self._apr_edit.setPlaceholderText("0.00")
        layout.addWidget(self._apr_edit)

        self._on_toggled(self._has_overdraft_check.isChecked())

        sts_title = QLabel("Safe to Spend Today")
        sts_title.setStyleSheet(ui_scale.style("font-size: 16px; font-weight: bold;"))
        layout.addWidget(sts_title)

        sts_info = QLabel(
            "The buffer is the balance Safe to Spend Today never plans to go below."
        )
        sts_info.setWordWrap(True)
        sts_info.setObjectName(label_roles.SUBTLE)
        layout.addWidget(sts_info)

        layout.addWidget(QLabel(f"Buffer ({get_symbol()}):"))
        self._floor_edit = QLineEdit()
        self._floor_edit.setText(f"{self._safe_to_spend_floor.pounds:.2f}")
        self._floor_edit.setPlaceholderText("0.00")
        layout.addWidget(self._floor_edit)

        layout.addWidget(QLabel("Months the figure must keep standing:"))
        self._window_spin = QSpinBox()
        self._window_spin.setMinimum(_MIN_WINDOW_MONTHS)
        self._window_spin.setMaximum(_MAX_WINDOW_MONTHS)
        self._window_spin.setValue(self._sustainable_window_months)
        self._window_spin.setToolTip(
            "Every day of this many months must clear the buffer. A longer"
            " window is a harder promise, so the figure it allows is smaller."
        )
        layout.addWidget(self._window_spin)

        currency_title = QLabel("Display Currency")
        currency_title.setStyleSheet(
            ui_scale.style("font-size: 16px; font-weight: bold;")
        )
        layout.addWidget(currency_title)

        currency_info = QLabel(
            "The symbol shown throughout the app. Takes effect immediately"
            " after saving."
        )
        currency_info.setWordWrap(True)
        currency_info.setObjectName(label_roles.SUBTLE)
        layout.addWidget(currency_info)

        self._currency_combo = ThemedComboBox()
        self._currency_combo.setMinimumHeight(ui_scale.px(32))
        current_index = 0
        for i, c in enumerate(CURRENCIES):
            self._currency_combo.addItem(
                f"{c.symbol}  {c.code} - {c.name}", userData=c.code
            )
            if c.code == self._currency_code:
                current_index = i
        self._currency_combo.setCurrentIndex(current_index)
        layout.addWidget(self._currency_combo)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def _on_toggled(self, checked: bool) -> None:
        self._limit_edit.setEnabled(checked)
        self._apr_edit.setEnabled(checked)

    def _on_save(self) -> None:
        if not self._read_safe_to_spend_inputs():
            return
        if not self._has_overdraft_check.isChecked():
            self._new_overdraft_limit = Amount(pence=0)
            self._new_overdraft_apr_basis_points = 0
            self.accept()
            return
        try:
            limit_pence = field_pence(
                self._limit_edit, label=_LIMIT_LABEL, when_empty=0
            )
            apr_basis_points = apr_basis_points_from_text(self._apr_edit.text())
        except AmountFieldRefused as refusal:
            self._refuse_amount(refusal.field, refusal)
            return
        except InvalidRateError as refusal:
            self._refuse_amount(self._apr_edit, refusal)
            return
        self._new_overdraft_limit = Amount(pence=limit_pence)
        self._new_overdraft_apr_basis_points = apr_basis_points
        self.accept()

    def _read_safe_to_spend_inputs(self) -> bool:
        """Validate and stage the safe-to-spend fields; False keeps the dialog."""
        try:
            floor_pence = field_pence(
                self._floor_edit, label=_FLOOR_LABEL, when_empty=0
            )
        except AmountFieldRefused as refusal:
            self._refuse_amount(refusal.field, refusal)
            return False
        self._new_safe_to_spend_floor = Amount(pence=floor_pence)
        self._new_sustainable_window_months = self._window_spin.value()
        return True

    @property
    def currency_code(self) -> str:
        """The display currency the combo currently offers."""
        return self._currency_combo.currentData()

    @property
    def overdraft_limit(self) -> Amount | None:
        """New overdraft limit; None if the dialog was cancelled or invalid."""
        return self._new_overdraft_limit

    @property
    def overdraft_apr_basis_points(self) -> int | None:
        """New overdraft APR in basis points; None if cancelled or invalid."""
        return self._new_overdraft_apr_basis_points

    @property
    def safe_to_spend_floor(self) -> Amount | None:
        """New buffer; None if the dialog was cancelled or invalid."""
        return self._new_safe_to_spend_floor

    @property
    def sustainable_window_months(self) -> int | None:
        """New window length in months; None if cancelled or invalid."""
        return self._new_sustainable_window_months
