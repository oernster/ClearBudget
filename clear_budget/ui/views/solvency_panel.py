"""Solvency panel widget - displays financial health status and warnings."""

from datetime import date as _date

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton
from PySide6.QtCore import Qt

from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.utils.format_helpers import MONTH_NAMES


class SolvencyPanel(QWidget):
    """Displays account solvency status with three critical sections."""

    def __init__(self, view_model: SolvencyViewModel) -> None:
        """Initialize solvency panel widget."""
        super().__init__()
        self.view_model = view_model
        self.init_ui()
        self.connect_signals()

    def init_ui(self) -> None:
        """Build solvency panel layout with three sections."""
        layout = QVBoxLayout()

        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.month_label = QLabel("May 2026")
        self.month_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px; color: #9ca3af;")
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_btn = QPushButton("Next →")
        self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.month_label, stretch=1)
        nav_layout.addWidget(self.next_btn)
        layout.addLayout(nav_layout)

        # SECTION 1: OVERDRAFT ALERT (Top - Prominent)
        alert_label = QLabel("Overdraft Status")
        alert_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 10px;")
        layout.addWidget(alert_label)

        self.overdraft_alert = QLabel("SAFE: £0.00 buffer")
        self.overdraft_alert.setStyleSheet(
            "font-size: 16px; font-weight: bold; padding: 10px; border-radius: 5px;"
        )
        layout.addWidget(self.overdraft_alert)

        # SECTION 2: OVERALL HEALTH (Middle)
        health_label = QLabel("Overall Health")
        health_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 20px;")
        layout.addWidget(health_label)

        self.balance_label = QLabel("Bank Balance: £0.00")
        self.balance_label.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(self.balance_label)

        self.committed_label = QLabel("Committed this month: -")
        self.committed_label.setStyleSheet("font-size: 13px; padding: 5px; color: #9ca3af;")
        layout.addWidget(self.committed_label)

        self.remaining_label = QLabel("Still due this month: -")
        self.remaining_label.setStyleSheet("font-size: 13px; padding: 5px; color: #fbbf24;")
        layout.addWidget(self.remaining_label)

        self.card_util_label = QLabel("Credit Card Utilization: 0%")
        self.card_util_label.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(self.card_util_label)

        self.health_score_label = QLabel("Health Score: 0/100")
        self.health_score_label.setStyleSheet("font-size: 14px; padding: 5px; font-weight: bold;")
        layout.addWidget(self.health_score_label)

        self.health_bar = QProgressBar()
        self.health_bar.setMaximum(100)
        self.health_bar.setStyleSheet("QProgressBar { border-radius: 5px; }")
        layout.addWidget(self.health_bar)

        # SECTION 3: FORWARD PROJECTION (Bottom)
        forward_label = QLabel("Forward Projection")
        forward_label.setStyleSheet("font-weight: bold; font-size: 12px; margin-top: 20px;")
        layout.addWidget(forward_label)

        self.projection_label = QLabel("Safe for 0 days")
        self.projection_label.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(self.projection_label)

        self.forward_shortfall_label = QLabel("Forward Shortfall: £0.00")
        self.forward_shortfall_label.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(self.forward_shortfall_label)

        layout.addStretch()
        self.setLayout(layout)

    def connect_signals(self) -> None:
        """Connect ViewModel signals to view updates."""
        self.view_model.solvency_updated.connect(self.update_display)

    def _calculate_card_utilization(self) -> float:
        """Calculate combined credit card utilization percentage."""
        cards = self.view_model.budget_service.get_credit_cards(include_inactive=False)
        if not cards:
            return 0.0
        total_limit = sum(c.credit_limit.pence for c in cards)
        total_used = sum(c.current_balance_used.pence for c in cards)
        return (total_used / total_limit * 100) if total_limit > 0 else 0.0

    def _calculate_health_score(self, balance_pence: int, card_util: float) -> int:
        """Calculate health score (0-100) combining bank balance and card utilization."""
        # Bank balance component (60% weight): safe if > £1000
        bank_score = min(100, max(0, (balance_pence / 100) / 10))

        # Card utilization component (40% weight): good if < 50%
        card_score = max(0, 100 - (card_util * 2))

        return int(bank_score * 0.6 + card_score * 0.4)

    def _calculate_days_safe(self, balance_pence: int, first_negative_day: int | None) -> int:
        """Calculate how many days account stays safe (positive balance)."""
        if first_negative_day is None or balance_pence >= 0:
            return 999  # Indefinite safety
        return max(1, first_negative_day)

    def update_display(self, report) -> None:
        """Update display from solvency report."""
        if not report:
            return

        # HEADER: Update month/year
        month_name = MONTH_NAMES[report.year_month.month]
        self.month_label.setText(f"{month_name} {report.year_month.year}")

        # SECTION 1: OVERDRAFT ALERT
        balance = report.balance_pence / 100
        buffer_pounds = report.buffer.pounds
        base_style = "font-size: 16px; font-weight: bold; padding: 10px; border-radius: 5px; "
        if balance < 0:
            self.overdraft_alert.setText(f"AT RISK: Needs £{abs(balance):.2f}")
            self.overdraft_alert.setStyleSheet(base_style + "background-color: #f87171; color: white;")
        elif balance < buffer_pounds:
            self.overdraft_alert.setText(f"TIGHT: £{buffer_pounds - balance:.2f} below buffer")
            self.overdraft_alert.setStyleSheet(base_style + "background-color: #f59e0b; color: white;")
        else:
            self.overdraft_alert.setText(f"SAFE: £{balance - buffer_pounds:.2f} above buffer")
            self.overdraft_alert.setStyleSheet(base_style + "background-color: #34d399; color: white;")

        # SECTION 2: OVERALL HEALTH
        self.balance_label.setText(f"Projected Balance: £{balance:.2f}")

        today = _date.today()
        summary = self.view_model.current_summary
        if (report.year_month.year == today.year and report.year_month.month == today.month
                and summary):
            committed = sum(b.amount.pence for b in summary.bills
                            if b.day_of_month and b.day_of_month < today.day)
            remaining = sum(b.amount.pence for b in summary.bills
                            if not b.day_of_month or b.day_of_month >= today.day)
            self.committed_label.setText(f"Committed this month: £{committed / 100:.2f}")
            self.remaining_label.setText(f"Still due this month: £{remaining / 100:.2f}")
        else:
            self.committed_label.setText("Committed this month: -")
            self.remaining_label.setText("Still due this month: -")

        card_util = self._calculate_card_utilization()
        self.card_util_label.setText(f"Credit Card Utilization: {card_util:.1f}%")

        health_score = self._calculate_health_score(report.balance_pence, card_util)
        self.health_score_label.setText(f"Health Score: {health_score}/100")
        self.health_bar.setValue(health_score)
        if health_score < 34:
            bar_color = "#f87171"
        elif health_score < 67:
            bar_color = "#f59e0b"
        else:
            bar_color = "#34d399"
        self.health_bar.setStyleSheet(
            f"QProgressBar {{ border-radius: 5px; }} "
            f"QProgressBar::chunk {{ background-color: {bar_color}; }}"
        )

        # SECTION 3: FORWARD PROJECTION
        days_safe = self._calculate_days_safe(report.balance_pence, report.first_negative_day)
        if days_safe == 999:
            self.projection_label.setText("Safe indefinitely")
        else:
            self.projection_label.setText(f"Safe for {days_safe} days")

        forward_str = f"£{report.forward_shortfall.pounds:.2f}"
        self.forward_shortfall_label.setText(f"Forward Shortfall: {forward_str}")
