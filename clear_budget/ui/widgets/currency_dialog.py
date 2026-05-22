"""CurrencyDialog - lets the user pick a display currency."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
)

from clear_budget.shared.currency import CURRENCIES, Currency
from clear_budget.ui import ui_scale


class CurrencyDialog(QDialog):
    """Simple picker dialog for selecting a display currency."""

    def __init__(self, current_code: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences - Currency")
        self.setMinimumWidth(ui_scale.px(420))
        self._selected_code = current_code
        self._build_ui(current_code)

    def _build_ui(self, current_code: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(ui_scale.px(10))
        layout.setContentsMargins(
            ui_scale.px(24), ui_scale.px(20), ui_scale.px(24), ui_scale.px(20)
        )

        title = QLabel("Display Currency")
        title.setStyleSheet(ui_scale.style("font-size: 16px; font-weight: bold;"))
        layout.addWidget(title)

        info = QLabel(
            "Choose the currency symbol shown throughout the app.\n"
            "The change takes effect immediately after saving."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(info)

        self._combo = QComboBox()
        self._combo.setMinimumHeight(ui_scale.px(32))
        current_index = 0
        for i, c in enumerate(CURRENCIES):
            self._combo.addItem(f"{c.symbol}  {c.code} - {c.name}", userData=c.code)
            if c.code == current_code:
                current_index = i
        self._combo.setCurrentIndex(current_index)
        layout.addWidget(self._combo)

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

    def _on_save(self) -> None:
        self._selected_code = self._combo.currentData()
        self.accept()

    @property
    def selected_code(self) -> str:
        """Currency code chosen by the user."""
        return self._selected_code
