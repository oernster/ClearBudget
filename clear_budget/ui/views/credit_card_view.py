"""Credit card view widget - displays credit card status and exhaustion warnings."""

import dataclasses

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QPushButton,
    QHeaderView,
    QGroupBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from clear_budget.domain.value_objects.amount import Amount
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.shared.currency import get_symbol
from clear_budget.ui.widgets.credit_card_dialog import CreditCardDialog
from clear_budget.ui import ui_scale
from clear_budget.ui.utils.format_helpers import build_nav_month_widget
from clear_budget.ui.views._credit_card_view_loaders import (
    CreditCardViewLoaderMixin,
    _PROJECTION_MONTHS,
)


class CreditCardView(CreditCardViewLoaderMixin, QWidget):
    """Displays credit card status with exhaustion warnings."""

    def __init__(
        self,
        budget_service: BudgetService,
        current_month: YearMonth = YearMonth(2026, 5),
    ) -> None:
        """Initialize credit card view widget."""
        super().__init__()
        self.budget_service = budget_service
        self.current_month = current_month
        self.init_ui()
        self.load_cards()

    def init_ui(self) -> None:
        """Build credit card view layout."""
        layout = QVBoxLayout()

        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_btn = QPushButton("Next →")
        self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _nav_center, self.month_label = build_nav_month_widget("")
        left_group = QWidget()
        left_lo = QHBoxLayout(left_group)
        left_lo.setContentsMargins(0, 0, 0, 0)
        left_lo.addWidget(self.prev_btn)
        left_lo.addStretch()
        right_group = QWidget()
        right_lo = QHBoxLayout(right_group)
        right_lo.setContentsMargins(0, 0, 0, 0)
        right_lo.addStretch()
        right_lo.addWidget(self.next_btn)
        nav_layout.addWidget(left_group, 1)
        nav_layout.addWidget(_nav_center, 0)
        nav_layout.addWidget(right_group, 1)
        layout.addLayout(nav_layout)
        self._refresh_month_label()

        cards_group = QGroupBox("Credit Cards")
        cards_layout = QVBoxLayout()

        self.cards_table = QTableWidget()
        self.cards_table.setColumnCount(15)
        self.cards_table.setHorizontalHeaderLabels(
            [
                "Card Name",
                "Limit",
                "Used",
                "Available",
                "Util %",
                "Due Day",
                "Interest %",
                f"Fixed Min ({get_symbol()})",
                "Expiry",
                "Status",
                "Active",
                "Month Charges",
                "Payment Received",
                "Month Interest",
                "Min Payment Due",
            ]
        )
        self.cards_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.cards_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.cards_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)
        self.cards_table.itemChanged.connect(self._on_card_item_changed)
        _ch = self.cards_table.horizontalHeader()
        _ch.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        _ch.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        _ch.setStretchLastSection(False)
        self.cards_table.setStyleSheet(
            "QTableWidget::indicator{width:15px;height:15px;border:2px solid #9ca3af;"
            "border-radius:3px;background:transparent;}"
            "QTableWidget::indicator:checked{background:#34d399;border-color:#34d399;}"
            "QTableWidget::indicator:unchecked:hover{border-color:#d1d5db;}"
        )
        self.cards_table.verticalHeader().setStyleSheet(
            "QHeaderView::section { color: #34d399; }"
        )
        self.cards_table.verticalHeader().sectionClicked.connect(
            self._on_card_row_header_click
        )
        self.cards_table.cellClicked.connect(self._on_card_cell_clicked)
        cards_layout.addWidget(self.cards_table)

        # Buttons below table
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Card")
        self.edit_btn = QPushButton("Edit Card")
        self.delete_btn = QPushButton("Delete Card")
        self.delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        cards_layout.addLayout(btn_layout)

        cards_group.setLayout(cards_layout)
        layout.addWidget(cards_group)

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

        # Connect buttons
        self.add_btn.clicked.connect(self.on_add_card)
        self.edit_btn.clicked.connect(self.on_edit_card)
        self.delete_btn.clicked.connect(self.on_delete_card)

    def _on_card_cell_clicked(self, row: int, col: int) -> None:
        if col != 10:
            return
        from PySide6.QtWidgets import QApplication

        mods = QApplication.keyboardModifiers()
        item = self.cards_table.item(row, 10)
        if not item:
            return
        card_id = item.data(Qt.ItemDataRole.UserRole)
        if mods & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            self.cards_table.blockSignals(True)
            cursor = self.budget_service.payment_method_repo.conn.cursor()
            cursor.execute("SELECT active FROM credit_cards WHERE id=?", (card_id,))
            r = cursor.fetchone()
            if r:
                item.setCheckState(
                    Qt.CheckState.Checked
                    if r["active"] == 1
                    else Qt.CheckState.Unchecked
                )
            self.cards_table.blockSignals(False)
            return
        active = item.checkState() == Qt.CheckState.Checked
        self.budget_service.payment_method_repo.set_card_active(
            card_id=card_id, active=active
        )
        self.load_cards()

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

    def _on_card_row_header_click(self, row: int) -> None:
        """Handle pencil icon click on card row header."""
        self.cards_table.selectRow(row)
        self.on_edit_card()

    def _card_id_from_row(self, row: int) -> int | None:
        item = self.cards_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def on_add_card(self) -> None:
        dialog = CreditCardDialog(self)
        if dialog.exec():
            card = dialog.get_card()
            if card:
                existing = self.budget_service.get_credit_cards(include_inactive=True)
                if any(c.name.lower() == card.name.lower() for c in existing):
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.warning(
                        self,
                        "Duplicate Card",
                        f"A card named '{card.name}' already exists.",
                    )
                    return
                self.budget_service.payment_method_repo.add_credit_card(card=card)
                self.load_cards()

    def on_edit_card(self) -> None:
        row = self.cards_table.currentRow()
        if row < 0:
            return
        card_id = self._card_id_from_row(row)
        if card_id is None:
            return
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

    _EDITABLE_COLS = {0, 1, 2, 5, 6, 7, 8}

    def _on_card_item_changed(self, item) -> None:
        if item.column() not in self._EDITABLE_COLS:
            QTimer.singleShot(0, self.load_cards)
            return
        card_id = self._card_id_from_row(item.row())
        if card_id is None:
            return
        card = self.budget_service.payment_method_repo.get_credit_card_by_id(
            card_id=card_id
        )
        if card is None:
            return
        col, v = item.column(), item.text().strip()
        try:
            if col == 0:
                u, d = dataclasses.replace(card, name=v or card.name), v or card.name
            elif col == 1:
                a = Amount.from_pounds(float(v.lstrip(get_symbol())))
                u, d = dataclasses.replace(card, credit_limit=a), str(a)
            elif col == 2:
                a = Amount.from_pounds(float(v.lstrip(get_symbol())))
                u, d = dataclasses.replace(card, current_balance_used=a), str(a)
            elif col == 5:
                u, d = dataclasses.replace(card, payment_due_day=int(v)), str(int(v))
            elif col == 6:
                apr = float(v.rstrip("%").strip()) if v != "-" else None
                u, d = dataclasses.replace(card, interest_rate_apr=apr), (
                    f"{apr:.2f}%" if apr else " - "
                )
            elif col == 7:
                pence = (
                    Amount.from_pounds(float(v.lstrip(get_symbol()))).pence
                    if v != "-"
                    else None
                )
                u, d = dataclasses.replace(card, minimum_payment_pence=pence), (
                    str(Amount(pence=pence)) if pence is not None else " - "
                )
            elif col == 8:
                if v == "-":
                    u, d = (
                        dataclasses.replace(
                            card, card_expiry_month=None, card_expiry_year=None
                        ),
                        " - ",
                    )
                else:
                    m, y2 = int(v.split("/")[0]), int(v.split("/")[1])
                    u, d = (
                        dataclasses.replace(
                            card,
                            card_expiry_month=m,
                            card_expiry_year=2000 + y2 if y2 < 100 else y2,
                        ),
                        f"{m:02d}/{y2:02d}",
                    )
            elif col == 14:
                pence = (
                    Amount.from_pounds(float(v.lstrip(get_symbol()))).pence
                    if v not in ("-", "")
                    else None
                )
                u, d = dataclasses.replace(card, minimum_payment_pence=pence), (
                    str(Amount(pence=pence)) if pence is not None else " - "
                )
            else:
                return
            if u == card:
                return  # nothing changed - editor just opened, don't rebuild
            self.budget_service.payment_method_repo.update_credit_card(card=u)
            self.cards_table.blockSignals(True)
            item.setText(d)
            self.cards_table.blockSignals(False)
            QTimer.singleShot(0, self.load_cards)
        except Exception:
            QTimer.singleShot(0, self.load_cards)

    def on_delete_card(self) -> None:
        selected_rows = sorted(
            {idx.row() for idx in self.cards_table.selectedIndexes()}
        )
        card_ids = [
            cid for row in selected_rows if (cid := self._card_id_from_row(row))
        ]
        for card_id in card_ids:
            self.budget_service.payment_method_repo.hard_delete_credit_card(
                card_id=card_id
            )
        if card_ids:
            self.load_cards()
