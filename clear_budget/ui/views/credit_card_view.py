"""Credit card view widget - displays credit card status and exhaustion warnings."""

from dataclasses import replace

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QHeaderView,
    QGroupBox,
    QTableWidget,
    QSizePolicy,
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

        # Cards stack directly in the group. The whole tab already lives inside a
        # ScrollableTab, so a second inner scroll only stole height and left an
        # empty gap above the Add Card button whenever few cards were present.
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(ui_scale.px(8))
        cards_outer_layout.addWidget(self.cards_container)

        # Buttons below the card list
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Card")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addStretch()
        cards_outer_layout.addLayout(btn_layout)

        cards_group.setLayout(cards_outer_layout)
        layout.addWidget(cards_group, 0)

        proj_group = QGroupBox(f"{_PROJECTION_MONTHS}-Month Balance Projection")
        proj_layout = QVBoxLayout()
        self.projection_table = QTableWidget()
        self.projection_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.projection_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        _ph = self.projection_table.horizontalHeader()
        _ph.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Columns always stretch to fit, so no horizontal scrollbar is ever
        # needed; turning it off keeps it from eating into the fixed height and
        # clipping the final month row.
        self.projection_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.projection_table.verticalHeader().setDefaultSectionSize(ui_scale.px(28))
        # The strip is locked to exactly its rows in _build_projection_strip,
        # once the columns (and so the real header height) are populated.
        proj_layout.addWidget(self.projection_table)
        proj_group.setLayout(proj_layout)
        proj_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        layout.addWidget(proj_group, 0)
        # With few cards the content is shorter than the tab: let the slack fall
        # to the bottom so the card list and projection stay compact at the top,
        # rather than the card list stretching and pushing the projection off.
        layout.addStretch(1)

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
                new_id = self.budget_service.save_credit_card_today_balance(
                    card=card, today_balance=card.current_balance_used, is_new=True
                )
                self.budget_service.set_credit_limit_changes(
                    card_id=new_id, changes=dialog.get_limit_changes()
                )
                self.load_cards()

    def on_edit_card(self, card_id: int) -> None:
        card = self.budget_service.payment_method_repo.get_credit_card_by_id(
            card_id=card_id
        )
        if not card:
            return
        # Pre-fill with the live balance shown as "Used" so the field reflects
        # what the user owes now; the save path re-anchors it to today.
        live_balance = self.budget_service.get_live_card_balance(card=card)
        dialog = CreditCardDialog(
            self, replace(card, current_balance_used=live_balance)
        )
        if dialog.exec():
            updated_card = dialog.get_card()
            if updated_card:
                self.budget_service.save_credit_card_today_balance(
                    card=updated_card,
                    today_balance=updated_card.current_balance_used,
                    is_new=False,
                )
                self.budget_service.set_credit_limit_changes(
                    card_id=updated_card.id, changes=dialog.get_limit_changes()
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
