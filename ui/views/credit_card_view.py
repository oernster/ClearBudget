from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QProgressBar,
    QScrollArea,
)
from PySide6.QtCore import Qt
from models.month import Month


class CreditCardView(QWidget):
    def __init__(self, db, year_month):
        super().__init__()
        self.db = db
        self.year_month = year_month

        layout = QVBoxLayout()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()

        # Get all credit cards
        cursor = db.execute(
            'SELECT id, name, credit_limit, current_balance_used FROM payment_methods WHERE type = "credit_card" ORDER BY name'
        )
        cards = cursor.fetchall()

        for card in cards:
            scroll_layout.addWidget(self._build_card_widget(card))

        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)

        layout.addWidget(scroll)
        self.setLayout(layout)

    def _build_card_widget(self, card):
        """Build a credit card status widget."""
        group = QGroupBox(card["name"])
        layout = QVBoxLayout()

        # Balance bar
        limit = card["credit_limit"]
        used = card["current_balance_used"]
        available = limit - used
        percent = int((used / limit) * 100) if limit > 0 else 0

        bar = QProgressBar()
        bar.setValue(percent)
        bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: """
            + ("red" if percent > 90 else "orange" if percent > 75 else "green")
            + """;
            }
        """
        )

        layout.addWidget(bar)

        # Stats
        stats = QLabel(
            f"Used: £{used:.2f} / Limit: £{limit:.2f} | Available: £{available:.2f}"
        )
        layout.addWidget(stats)

        # Bills on this card
        month_data = Month.get_month_data(self.db, self.year_month)
        bills_on_card = [
            b for b in month_data["bills"] if b["payment_method_id"] == card["id"]
        ]

        if bills_on_card:
            bills_label = QLabel("Bills on card:")
            layout.addWidget(bills_label)
            for bill in bills_on_card:
                bill_label = QLabel(f"  • {bill['name']}: £{bill['amount']:.2f}")
                layout.addWidget(bill_label)

        group.setLayout(layout)
        return group

    def update_month(self, year_month):
        """Update to new month."""
        self.year_month = year_month
        # Refresh would need UI rebuild - for now just update year_month
