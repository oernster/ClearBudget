"""Credit card view widget - displays credit card status and exhaustion warnings."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QHeaderView,
    QGroupBox,
    QScrollArea,
    QTableWidget,
    QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.widgets.credit_card_dialog import CreditCardDialog
from clear_budget.ui import ui_scale
from clear_budget.ui.utils.format_helpers import (
    apply_nav_label_color,
    build_centered_nav_header,
)
from clear_budget.ui.views._credit_card_view_loaders import (
    CreditCardViewLoaderMixin,
    _PROJECTION_MONTHS,
)


class CreditCardView(CreditCardViewLoaderMixin, QWidget):
    """Displays credit card status with exhaustion warnings."""

    def __init__(
        self,
        budget_service: BudgetService,
        current_month: YearMonth | None = None,
        read_only: bool = False,
    ) -> None:
        """Initialize credit card view widget."""
        super().__init__()
        self.budget_service = budget_service
        self.current_month = current_month or YearMonth.today()
        self.read_only = read_only
        self.init_ui()
        self.load_cards()

    def init_ui(self) -> None:
        """Build credit card view layout."""
        layout = QVBoxLayout()

        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_btn = QPushButton("Next →")
        self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.nav_header, self.month_label = build_centered_nav_header(
            "", prev_btn=self.prev_btn, next_btn=self.next_btn
        )
        self._refresh_month_label()

        cards_group = QGroupBox("Credit Cards")
        cards_outer_layout = QVBoxLayout()

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(ui_scale.px(8))

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.cards_scroll.setWidget(self.cards_container)
        cards_outer_layout.addWidget(self.cards_scroll)

        # Buttons below the card list
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Card")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addStretch()
        cards_outer_layout.addLayout(btn_layout)

        cards_group.setLayout(cards_outer_layout)
        layout.addWidget(cards_group, 1)

        proj_group = QGroupBox(f"{_PROJECTION_MONTHS}-Month Balance Projection")
        proj_layout = QVBoxLayout()
        self.projection_table = QTableWidget()
        self.projection_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.projection_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        _ph = self.projection_table.horizontalHeader()
        _ph.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.projection_table.verticalHeader().setDefaultSectionSize(ui_scale.px(28))
        proj_layout.addWidget(self.projection_table)
        proj_group.setLayout(proj_layout)
        layout.addWidget(proj_group)

        self.setLayout(layout)

        self.add_btn.clicked.connect(self.on_add_card)

        if self.read_only:
            self.add_btn.setEnabled(False)

    def set_month(self, year_month: YearMonth) -> None:
        """Update displayed month and refresh."""
        object.__setattr__(self, "current_month", year_month)
        self._refresh_month_label()
        self.load_cards()

    def _refresh_month_label(self) -> None:
        from clear_budget.ui.utils.format_helpers import MONTH_NAMES

        self.month_label.setText(
            f"{MONTH_NAMES[self.current_month.month]} {self.current_month.year}"
        )

    def set_nav_label_color(self, color: str) -> None:
        """Recolour the nav month label to match the Solvency tab."""
        apply_nav_label_color(self.month_label, color)

    def _get_status_text(self, utilization: float) -> str:
        """Get status text based on card utilization."""
        if utilization >= 80:
            return "DANGER"
        if utilization >= 50:
            return "WARNING"
        return "OK"

    def _get_status_color(self, status: str) -> QColor:
        """Get color for status."""
        if status == "DANGER":
            return QColor("#f87171")  # Red
        if status == "WARNING":
            return QColor("#fbbf24")  # Yellow
        return QColor("#34d399")  # Green

    def on_add_card(self) -> None:
        dialog = CreditCardDialog(self)
        if dialog.exec():
            card = dialog.get_card()
            if card:
                existing = self.budget_service.get_credit_cards(include_inactive=True)
                if any(c.name.lower() == card.name.lower() for c in existing):
                    QMessageBox.warning(
                        self,
                        "Duplicate Card",
                        f"A card named '{card.name}' already exists.",
                    )
                    return
                self.budget_service.payment_method_repo.add_credit_card(card=card)
                self.load_cards()

    def on_edit_card(self, card_id: int) -> None:
        card = self.budget_service.payment_method_repo.get_credit_card_by_id(
            card_id=card_id
        )
        if not card:
            return
        dialog = CreditCardDialog(self, card)
        if dialog.exec():
            updated_card = dialog.get_card()
            if updated_card:
                self.budget_service.payment_method_repo.update_credit_card(
                    card=updated_card
                )
                self.load_cards()

    def on_delete_card(self, card_id: int, name: str) -> None:
        reply = QMessageBox.question(
            self,
            "Delete Card",
            f"Delete '{name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.budget_service.payment_method_repo.hard_delete_credit_card(card_id=card_id)
        self.load_cards()

    def _on_card_active_toggled(self, card_id: int, checked: bool) -> None:
        if self.read_only:
            return
        self.budget_service.payment_method_repo.set_card_active(
            card_id=card_id, active=checked
        )
        self.load_cards()
