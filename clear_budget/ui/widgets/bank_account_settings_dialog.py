"""BankAccountSettingsDialog - configure the overdraft facility."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
)

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.shared.currency import get_symbol
from clear_budget.ui import ui_scale

_BASIS_POINTS_PER_PERCENT = 100


class BankAccountSettingsDialog(QDialog):
    """Dialog for configuring the bank account's overdraft facility."""

    def __init__(
        self,
        parent=None,
        *,
        overdraft_limit: Amount | None = None,
        overdraft_apr_basis_points: int = 0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bank Account Settings")
        self.setMinimumWidth(ui_scale.px(420))
        self._overdraft_limit = overdraft_limit or Amount(pence=0)
        self._overdraft_apr_basis_points = overdraft_apr_basis_points
        self._new_overdraft_limit: Amount | None = None
        self._new_overdraft_apr_basis_points: int | None = None
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
            "If your bank account has an agreed overdraft, enter the limit and"
            " APR here. Clear Budget will use this to judge whether a mid-month"
            " dip below zero is covered by your facility."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #94a3b8; font-size: 12px;")
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
        if not self._has_overdraft_check.isChecked():
            self._new_overdraft_limit = Amount(pence=0)
            self._new_overdraft_apr_basis_points = 0
            self.accept()
            return
        try:
            limit_pounds = float(self._limit_edit.text().strip() or "0")
            apr_percent = float(self._apr_edit.text().strip() or "0")
        except ValueError:
            return
        if limit_pounds < 0 or apr_percent < 0:
            return
        self._new_overdraft_limit = Amount.from_pounds(limit_pounds)
        self._new_overdraft_apr_basis_points = round(
            apr_percent * _BASIS_POINTS_PER_PERCENT
        )
        self.accept()

    @property
    def overdraft_limit(self) -> Amount | None:
        """New overdraft limit, or None if dialog was cancelled/invalid."""
        return self._new_overdraft_limit

    @property
    def overdraft_apr_basis_points(self) -> int | None:
        """New overdraft APR in basis points, or None if cancelled/invalid."""
        return self._new_overdraft_apr_basis_points
