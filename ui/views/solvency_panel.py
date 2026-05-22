from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, Qt as QtCore_Qt
from services.solvency_calculator import SolvencyCalculator


class SolvencyPanel(QWidget):
    def __init__(self, db, year_month):
        super().__init__()
        self.db = db
        self.year_month = year_month

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("SOLVENCY CHECK")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        # Main metrics row
        metrics_layout = QHBoxLayout()

        # Current month balance
        self.balance_label = QLabel()
        metrics_layout.addWidget(self.balance_label)

        metrics_layout.addSpacing(20)

        # Deficit warning
        self.deficit_label = QLabel()
        metrics_layout.addWidget(self.deficit_label)

        metrics_layout.addSpacing(20)

        # Desired acquire
        self.acquire_label = QLabel()
        metrics_layout.addWidget(self.acquire_label)

        metrics_layout.addStretch()

        layout.addLayout(metrics_layout)

        # Card warnings row
        self.warnings_label = QLabel()
        self.warnings_label.setWordWrap(True)
        layout.addWidget(self.warnings_label)

        self.setLayout(layout)

        # Style
        self.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
                border-radius: 4px;
                padding: 10px;
            }
        """)

        self._refresh()

    def _refresh(self):
        """Refresh solvency data."""
        current = SolvencyCalculator.calculate_current_month(self.db, self.year_month)
        solvency = SolvencyCalculator.calculate_desired_acquire(
            self.db, self.year_month
        )
        cards = SolvencyCalculator.check_card_exhaustion(self.db, self.year_month)

        # Balance
        balance = current["balance"]
        balance_color = "green" if balance >= 0 else "red"
        self.balance_label.setText(
            f"Balance: <span style='color: {balance_color}; font-weight: bold;'>£{balance:.2f}</span>"
        )
        self.balance_label.setTextFormat(Qt.TextFormat.RichText)

        # Deficit
        if solvency["deficit"] > 0:
            self.deficit_label.setText(
                f"Deficit: <span style='color: red; font-weight: bold;'>£{solvency['deficit']:.2f}</span>"
            )
            self.deficit_label.setTextFormat(Qt.TextFormat.RichText)
        else:
            self.deficit_label.setText("Deficit: None")

        # Desired acquire
        if solvency["desired_acquire"] > 0:
            self.acquire_label.setText(
                f"Acquire needed: <span style='color: darkred; font-weight: bold;'>£{solvency['desired_acquire']:.2f}</span> (£{solvency['deficit']:.2f} deficit + £600 buffer + £{solvency['forward_shortfall']:.2f} forward)"
            )
            self.acquire_label.setTextFormat(Qt.TextFormat.RichText)
        else:
            self.acquire_label.setText("Acquire needed: None")

        # Card warnings
        if cards:
            warnings_text = "⚠️ Card warnings: "
            warnings_list = []
            for card in cards:
                status_emoji = "🔴" if card["status"] == "danger" else "🟡"
                warnings_list.append(
                    f"{status_emoji} {card['card']}: £{card['available']:.0f} available, "
                    f"£{card['monthly_charge']:.0f}/mo charge - £{card['monthly_payment']:.0f}/mo payment = "
                    f"+£{card['net_monthly']:.0f}/mo (max out in {card['months_until_max']:.1f} months)"
                )
            warnings_text += " | ".join(warnings_list)
            self.warnings_label.setText(warnings_text)
            self.warnings_label.setStyleSheet("color: darkred; font-weight: bold;")
        else:
            self.warnings_label.setText("")

    def update_month(self, year_month):
        """Update to new month."""
        self.year_month = year_month
        self._refresh()
