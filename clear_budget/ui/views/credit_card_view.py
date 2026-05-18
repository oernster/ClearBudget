"""Credit card view widget - displays credit card status and exhaustion warnings."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.ui.widgets.credit_card_dialog import CreditCardDialog


class CreditCardView(QWidget):
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

        from PySide6.QtWidgets import QGroupBox
        cards_group = QGroupBox("Credit Cards")
        cards_layout = QVBoxLayout()

        self.cards_table = QTableWidget()
        self.cards_table.setColumnCount(11)
        self.cards_table.setHorizontalHeaderLabels(
            [
                "Card Name",
                "Limit",
                "Used",
                "Available",
                "Util %",
                "Due Day",
                "Interest %",
                "Min Pmt",
                "Expiry",
                "Status",
                "Active",
            ]
        )
        self.cards_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.cards_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.cards_table.verticalHeader().setStyleSheet("QHeaderView::section { color: #34d399; }")
        self.cards_table.verticalHeader().sectionClicked.connect(self._on_card_row_header_click)
        cards_layout.addWidget(self.cards_table)

        # Buttons below table
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Card")
        self.edit_btn = QPushButton("Edit Card")
        self.delete_btn = QPushButton("Delete Card")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        cards_layout.addLayout(btn_layout)

        cards_group.setLayout(cards_layout)
        layout.addWidget(cards_group)

        self.setLayout(layout)

        # Connect buttons
        self.add_btn.clicked.connect(self.on_add_card)
        self.edit_btn.clicked.connect(self.on_edit_card)
        self.delete_btn.clicked.connect(self.on_delete_card)

    def load_cards(self) -> None:
        """Load and display credit cards."""
        self.cards_table.setRowCount(0)

        cards = self.budget_service.get_credit_cards(include_inactive=False)
        if not cards:
            empty_item = QTableWidgetItem("No credit cards configured")
            empty_item.setForeground(Qt.GlobalColor.gray)
            self.cards_table.insertRow(0)
            self.cards_table.setItem(0, 0, empty_item)
            return

        for card in cards:
            row = self.cards_table.rowCount()
            self.cards_table.insertRow(row)
            self.cards_table.setVerticalHeaderItem(row, QTableWidgetItem("📝"))

            self.cards_table.setItem(row, 0, QTableWidgetItem(card.name))
            self.cards_table.setItem(row, 1, QTableWidgetItem(str(card.credit_limit)))
            self.cards_table.setItem(
                row, 2, QTableWidgetItem(str(card.current_balance_used))
            )
            self.cards_table.setItem(row, 3, QTableWidgetItem(str(card.available)))

            util_item = QTableWidgetItem(f"{card.utilization_percent:.1f}%")
            self.cards_table.setItem(row, 4, util_item)

            # Due day
            self.cards_table.setItem(row, 5, QTableWidgetItem(str(card.payment_due_day)))

            # Interest rate
            interest_str = f"{card.interest_rate_apr:.1f}%" if card.interest_rate_apr else " - "
            self.cards_table.setItem(row, 6, QTableWidgetItem(interest_str))

            # Minimum payment
            if card.minimum_payment_pence is not None:
                from clear_budget.domain.value_objects.amount import Amount
                min_pmt = Amount(pence=card.minimum_payment_pence)
                min_pmt_str = str(min_pmt)
            else:
                min_pmt_str = " - "
            self.cards_table.setItem(row, 7, QTableWidgetItem(min_pmt_str))

            # Expiry
            if card.card_expiry_month and card.card_expiry_year:
                expiry_str = f"{card.card_expiry_month:02d}/{card.card_expiry_year % 100:02d}"
            else:
                expiry_str = " - "
            self.cards_table.setItem(row, 8, QTableWidgetItem(expiry_str))

            status = self._get_status_text(card.utilization_percent)
            status_item = QTableWidgetItem(status)
            status_color = self._get_status_color(status)
            status_item.setForeground(Qt.GlobalColor.white)
            status_item.setBackground(status_color)
            self.cards_table.setItem(row, 9, status_item)

            # Active status
            active_str = "✓" if card.active == 1 else "✗"
            self.cards_table.setItem(row, 10, QTableWidgetItem(active_str))

    def set_month(self, year_month: YearMonth) -> None:
        """Update displayed month and refresh."""
        object.__setattr__(self, "current_month", year_month)
        self.load_cards()

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

    def on_add_card(self) -> None:
        """Handle add card button click."""
        print(f"[ADD_CARD] on_add_card() called")
        dialog = CreditCardDialog(self)
        if dialog.exec():
            card = dialog.get_card()
            print(f"[ADD_CARD] dialog.get_card() returned: {card}")
            if card:
                print(f"[ADD_CARD] Calling add_credit_card with: {card.name}")
                result = self.budget_service.payment_method_repo.add_credit_card(card=card)
                print(f"[ADD_CARD] add_credit_card returned: {result}")
                self.load_cards()
            else:
                print(f"[ADD_CARD] get_card() returned None")
        else:
            print(f"[ADD_CARD] Dialog was rejected")

    def on_edit_card(self) -> None:
        """Handle edit card button click."""
        row = self.cards_table.currentRow()
        if row < 0:
            return

        card_name = self.cards_table.item(row, 0).text()
        cards = self.budget_service.get_credit_cards(include_inactive=True)
        card = next((c for c in cards if c.name == card_name), None)

        if not card:
            return

        dialog = CreditCardDialog(self, card)
        if dialog.exec():
            updated_card = dialog.get_card()
            if updated_card:
                self.budget_service.payment_method_repo.update_credit_card(card=updated_card)
                self.load_cards()

    def on_delete_card(self) -> None:
        """Handle delete card button click."""
        row = self.cards_table.currentRow()
        print(f"[DELETE_CARD] on_delete_card() called, row={row}")
        if row < 0:
            print(f"[DELETE_CARD] No row selected, returning")
            return

        card_name = self.cards_table.item(row, 0).text()
        print(f"[DELETE_CARD] Card name from row: '{card_name}'")
        cards = self.budget_service.get_credit_cards(include_inactive=True)
        print(f"[DELETE_CARD] Found {len(cards)} cards (active + inactive)")
        card = next((c for c in cards if c.name == card_name), None)
        print(f"[DELETE_CARD] Matched card: {card}")

        if card:
            print(f"[DELETE_CARD] Deactivating card id={card.id}")
            self.budget_service.payment_method_repo.deactivate_credit_card(card_id=card.id)
            print(f"[DELETE_CARD] Calling load_cards()")
            self.load_cards()
        else:
            print(f"[DELETE_CARD] Card not found!")
