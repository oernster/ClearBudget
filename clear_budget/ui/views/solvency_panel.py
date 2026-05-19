"""Solvency panel widget - displays financial health status and warnings."""

from datetime import date as _date

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton
from PySide6.QtCore import Qt

from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.utils.format_helpers import MONTH_NAMES
from clear_budget.ui import ui_scale


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
        self.month_label.setStyleSheet(ui_scale.style("font-size: 20px; font-weight: bold; padding: 10px; color: #9ca3af;"))
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_btn = QPushButton("Next →")
        self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.month_label, stretch=1)
        nav_layout.addWidget(self.next_btn)
        layout.addLayout(nav_layout)

        # SECTION 1: OVERDRAFT ALERT (Top - Prominent)
        alert_label = QLabel("Overdraft Status")
        alert_label.setStyleSheet(ui_scale.style("font-weight: bold; font-size: 17px; margin-top: 10px;"))
        layout.addWidget(alert_label)

        self.overdraft_alert = QLabel("SAFE: £0.00 buffer")
        self.overdraft_alert.setStyleSheet(ui_scale.style(
            "font-size: 22px; font-weight: bold; padding: 10px; border-radius: 5px;"
        ))
        layout.addWidget(self.overdraft_alert)

        self.midmonth_alert = QLabel("")
        self.midmonth_alert.setWordWrap(True)
        self.midmonth_alert.setStyleSheet(ui_scale.style(
            "font-size: 18px; font-weight: bold; padding: 8px; border-radius: 5px; "
            "background-color: #dc2626; color: white;"
        ))
        self.midmonth_alert.hide()
        layout.addWidget(self.midmonth_alert)

        # SECTION 2: OVERALL HEALTH (Middle)
        health_label = QLabel("Overall Health")
        health_label.setStyleSheet(ui_scale.style("font-weight: bold; font-size: 17px; margin-top: 20px;"))
        layout.addWidget(health_label)

        self.freedom_label = QLabel("")
        self.freedom_label.setStyleSheet(ui_scale.style("font-size: 20px; font-weight: bold; padding: 5px; color: #34d399;"))
        layout.addWidget(self.freedom_label)

        self.balance_label = QLabel("Bank Balance: £0.00")
        self.balance_label.setStyleSheet(ui_scale.style("font-size: 20px; padding: 5px;"))
        layout.addWidget(self.balance_label)

        self.committed_label = QLabel("Committed this month: -")
        self.committed_label.setStyleSheet(ui_scale.style("font-size: 18px; padding: 5px; color: #9ca3af;"))
        layout.addWidget(self.committed_label)

        self.remaining_bank_label = QLabel("Still due this month (bank): -")
        self.remaining_bank_label.setWordWrap(True)
        self.remaining_bank_label.setStyleSheet(ui_scale.style("font-size: 18px; padding: 5px; color: #fbbf24;"))
        layout.addWidget(self.remaining_bank_label)

        self.remaining_card_label = QLabel("Still due this month (cards): -")
        self.remaining_card_label.setStyleSheet(ui_scale.style("font-size: 18px; padding: 5px; color: #f59e0b;"))
        layout.addWidget(self.remaining_card_label)

        self.card_util_label = QLabel("Credit Card Utilization: 0%")
        self.card_util_label.setStyleSheet(ui_scale.style("font-size: 20px; padding: 5px;"))
        layout.addWidget(self.card_util_label)

        self.health_score_label = QLabel("Health Score: 0/100")
        self.health_score_label.setStyleSheet(ui_scale.style("font-size: 20px; padding: 5px; font-weight: bold;"))
        layout.addWidget(self.health_score_label)

        self.health_bar = QProgressBar()
        self.health_bar.setMaximum(100)
        self.health_bar.setStyleSheet("QProgressBar { border-radius: 5px; }")
        layout.addWidget(self.health_bar)

        # SECTION 3: FORWARD PROJECTION (Bottom)
        forward_label = QLabel("Forward Projection")
        forward_label.setStyleSheet(ui_scale.style("font-weight: bold; font-size: 17px; margin-top: 20px;"))
        layout.addWidget(forward_label)

        self.projection_label = QLabel("Runway: calculating...")
        self.projection_label.setStyleSheet(ui_scale.style("font-size: 20px; padding: 5px;"))
        layout.addWidget(self.projection_label)

        self.forward_shortfall_label = QLabel("Next 2-month shortfall (bills − income): £0.00")
        self.forward_shortfall_label.setStyleSheet(ui_scale.style("font-size: 20px; padding: 5px;"))
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

    def update_display(self, report) -> None:
        """Update display from solvency report."""
        if not report:
            return

        # HEADER: Update month/year
        month_name = MONTH_NAMES[report.year_month.month]
        self.month_label.setText(f"{month_name} {report.year_month.year}")

        # SECTION 1: OVERDRAFT ALERT
        balance = report.balance_pence / 100
        today = _date.today()
        is_current_month = (report.year_month.year == today.year
                            and report.year_month.month == today.month)
        base_style = ui_scale.style("font-size: 22px; font-weight: bold; padding: 10px; border-radius: 5px; ")
        summary = self.view_model.current_summary
        monthly_deficit_pence = 0
        if not is_current_month and summary:
            bank_bills = sum(b.amount.pence for b in summary.bills if b.payment_method_id == 1)
            monthly_deficit_pence = bank_bills - summary.total_income.pence

        deficit_pounds = monthly_deficit_pence / 100
        deficit_note = f" (bills exceed income by £{deficit_pounds:.2f})" if monthly_deficit_pence > 0 else ""
        next_month_name = MONTH_NAMES[report.year_month.next_month().month]
        overdrawn_next_month = (monthly_deficit_pence > 0 and 0 < balance < monthly_deficit_pence / 100)
        if balance < 0:
            self.overdraft_alert.setText(f"CRITICAL: £{abs(balance):.2f} overdrawn{deficit_note}")
            self.overdraft_alert.setStyleSheet(base_style + "background-color: #f87171; color: white;")
        elif overdrawn_next_month:
            self.overdraft_alert.setText(
                f"CRITICAL: will be overdrawn in {next_month_name} — only £{balance:.2f} left in savings{deficit_note}"
            )
            self.overdraft_alert.setStyleSheet(base_style + "background-color: #f87171; color: white;")
        elif monthly_deficit_pence > 0 and balance <= 500:
            self.overdraft_alert.setText(
                f"CRITICAL: projected balance end of {month_name}: £{balance:.2f} — drawing down savings{deficit_note}"
            )
            self.overdraft_alert.setStyleSheet(base_style + "background-color: #f87171; color: white;")
        elif balance <= 200:
            self.overdraft_alert.setText(f"AT RISK: only £{balance:.2f} remaining{deficit_note}")
            self.overdraft_alert.setStyleSheet(base_style + "background-color: #f59e0b; color: white;")
        elif balance <= 500:
            self.overdraft_alert.setText(f"CAUTION: £{balance:.2f} remaining{deficit_note}")
            self.overdraft_alert.setStyleSheet(base_style + "background-color: #fbbf24; color: #1a1a1a;")
        elif monthly_deficit_pence > 0:
            self.overdraft_alert.setText(
                f"CAUTION: £{balance:.2f} after {month_name} bills{deficit_note}"
            )
            self.overdraft_alert.setStyleSheet(base_style + "background-color: #fbbf24; color: #1a1a1a;")
        else:
            self.overdraft_alert.setText(f"SAFE: £{balance:.2f} remaining after all {month_name} bills")
            self.overdraft_alert.setStyleSheet(base_style + "background-color: #34d399; color: white;")

        # MID-MONTH CASHFLOW CHECK (future months only)
        # Detects temporary overdraft when bills cluster before the last income payment
        self.midmonth_alert.hide()
        if not is_current_month and summary and summary.income_sources:
            income_days = [(i.day_of_month or 1, i.amount.pence) for i in summary.income_sources]
            max_income_day = max(d for d, _ in income_days)
            if max_income_day > 1:
                starting_pence = report.balance_pence - summary.total_income.pence + summary.bank_bills.pence
                early_income = sum(amt for day, amt in income_days if day < max_income_day)
                early_bills = sum(
                    b.amount.pence for b in summary.bills
                    if b.payment_method_id == 1 and (b.day_of_month or 1) < max_income_day
                )
                mid_balance = starting_pence + early_income - early_bills
                if mid_balance < 0:
                    self.midmonth_alert.setText(
                        f"CRITICAL: temporarily overdrawn by £{abs(mid_balance) / 100:.2f} "
                        f"before day-{max_income_day} income arrives — account rescued on day {max_income_day}"
                    )
                    self.midmonth_alert.show()

        # SECTION 2: OVERALL HEALTH
        self.balance_label.setText(f"Projected Balance: £{balance:.2f}")

        if summary:
            if is_current_month:
                committed = sum(b.amount.pence for b in summary.bills
                                if b.day_of_month and b.day_of_month < today.day)
                remaining_bank = sum(b.amount.pence for b in summary.bills
                                     if (not b.day_of_month or b.day_of_month >= today.day)
                                     and b.payment_method_id == 1)
                remaining_card = sum(b.amount.pence for b in summary.bills
                                     if (not b.day_of_month or b.day_of_month >= today.day)
                                     and b.payment_method_id != 1)
                self.committed_label.setText(f"Committed this month: £{committed / 100:.2f}")
                self.remaining_bank_label.setStyleSheet(ui_scale.style("font-size: 18px; padding: 5px; color: #fbbf24;"))
                self.remaining_bank_label.setText(f"Still due this month (bank): £{remaining_bank / 100:.2f}")
                self.remaining_card_label.setText(f"Still due this month (cards): £{remaining_card / 100:.2f}")
            else:
                all_bank = sum(b.amount.pence for b in summary.bills if b.payment_method_id == 1)
                all_card = sum(b.amount.pence for b in summary.bills if b.payment_method_id != 1)
                income_pence = summary.total_income.pence
                net_pence = all_bank - income_pence
                self.committed_label.setText("Committed this month: —")
                net_color = "#f87171" if net_pence > 0 else "#34d399"
                self.remaining_bank_label.setText(
                    f"Bank bills this month: £{all_bank / 100:.2f} vs income £{income_pence / 100:.2f}\n💰 projected end balance: £{balance:.2f}"
                )
                self.remaining_bank_label.setStyleSheet(ui_scale.style(f"font-size: 18px; padding: 5px; color: {net_color};"))
                self.remaining_card_label.setText(f"All bills this month (cards): £{all_card / 100:.2f}")
        else:
            self.committed_label.setText("Committed this month: -")
            self.remaining_bank_label.setText("Still due this month (bank): -")
            self.remaining_card_label.setText("Still due this month (cards): -")

        if summary:
            freedom_pence = summary.total_income.pence - summary.total_bills.pence
            if freedom_pence > 0:
                self.freedom_label.setText(f"Freedom to spend: £{freedom_pence / 100:.2f}")
                self.freedom_label.setStyleSheet(ui_scale.style("font-size: 20px; font-weight: bold; padding: 5px; color: #34d399;"))
            else:
                self.freedom_label.setText("No discretionary budget this month")
                self.freedom_label.setStyleSheet(ui_scale.style("font-size: 18px; padding: 5px; color: #9ca3af;"))
        else:
            self.freedom_label.setText("")

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
        shortfall_pence = report.forward_shortfall.pence
        if shortfall_pence == 0:
            self.projection_label.setText("Runway: income covers bills — no shortfall in next 2 months")
            self.projection_label.setStyleSheet(ui_scale.style("font-size: 20px; padding: 5px; color: #34d399;"))
        else:
            monthly_shortfall = shortfall_pence / 2
            if report.balance_pence <= 0:
                self.projection_label.setText("Runway: already in deficit")
                self.projection_label.setStyleSheet(ui_scale.style("font-size: 20px; padding: 5px; color: #f87171;"))
            else:
                months = report.balance_pence / monthly_shortfall
                self.projection_label.setText(
                    f"Runway: ~{months:.1f} months before overdraft at current spend rate"
                )
                color = "#f87171" if months < 2 else "#fbbf24" if months < 4 else "#34d399"
                self.projection_label.setStyleSheet(ui_scale.style(f"font-size: 20px; padding: 5px; color: {color};"))

        m1 = report.year_month.next_month()
        m2 = m1.next_month()
        m1_name = MONTH_NAMES[m1.month]
        m2_name = MONTH_NAMES[m2.month]
        monthly_gap = report.forward_shortfall.pence / 200  # pence → pounds, /2 months
        forward_str = f"£{report.forward_shortfall.pounds:.2f}"
        self.forward_shortfall_label.setText(
            f"Bills exceed income by £{monthly_gap:.2f}/month in {m1_name} & {m2_name} "
            f"(total shortfall: {forward_str})"
        )
