"""Solvency panel widget - displays financial health status and warnings."""

from datetime import date as _date

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton
from PySide6.QtCore import Qt

from clear_budget.domain.services.card_monthly_calculator import calculate_card_monthly_state
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.utils.format_helpers import MONTH_NAMES, build_nav_month_widget
from clear_budget.ui.dark_theme import SCROLLBAR_WIDTH_PX
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
        self.next_btn = QPushButton("Next →")
        self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _nav_center, self.month_label = build_nav_month_widget("May 2026")
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
        nav_layout.addSpacing(SCROLLBAR_WIDTH_PX)
        nav_layout.addWidget(left_group, 1)
        nav_layout.addWidget(_nav_center, 0)
        nav_layout.addWidget(right_group, 1)
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

        cards_header = QLabel("Credit Card Status")
        cards_header.setStyleSheet(ui_scale.style("font-weight: bold; font-size: 17px; margin-top: 10px;"))
        layout.addWidget(cards_header)

        self.card_bars_container = QWidget()
        self.card_bars_layout = QVBoxLayout(self.card_bars_container)
        self.card_bars_layout.setSpacing(ui_scale.px(3))
        self.card_bars_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.card_bars_container)

        # SECTION 3: FORWARD PROJECTION (Bottom)
        forward_label = QLabel("Forward Projection")
        forward_label.setStyleSheet(ui_scale.style("font-weight: bold; font-size: 17px; margin-top: 20px;"))
        layout.addWidget(forward_label)

        self.m1_projection_label = QLabel("")
        self.m1_projection_label.setWordWrap(True)
        self.m1_projection_label.setStyleSheet(ui_scale.style("font-size: 17px; padding: 5px;"))
        layout.addWidget(self.m1_projection_label)

        self.m2_projection_label = QLabel("")
        self.m2_projection_label.setWordWrap(True)
        self.m2_projection_label.setStyleSheet(ui_scale.style("font-size: 17px; padding: 5px;"))
        layout.addWidget(self.m2_projection_label)

        layout.addStretch()
        self.setLayout(layout)

    def connect_signals(self) -> None:
        """Connect ViewModel signals to view updates."""
        self.view_model.solvency_updated.connect(self.update_display)

    @staticmethod
    def _health_color(balance_pence: int, monthly_drain_pence: int) -> str:
        """Return traffic-light color based on balance vs monthly drain coverage.

        Red only for actual overdraft (< 0).
        Amber for positive but less than 2 months of drain coverage — tight but surviving.
        Green for 2+ months coverage.
        monthly_drain_pence: bills − income for a typical future month (positive = deficit).
        """
        if balance_pence < 0:
            return "#f87171"
        if monthly_drain_pence <= 0:
            return "#34d399"
        if balance_pence >= 2 * monthly_drain_pence:
            return "#34d399"
        return "#fbbf24"

    def _build_month_cashflow_summary(
        self, opening_pence: int, summary, monthly_drain_pence: int
    ) -> tuple[str, str]:
        """Build cashflow risk narrative for one month.

        Simulates events in day order. Returns (display_text, color).
        monthly_drain_pence used for amber/red thresholds.
        """
        events = []
        for inc in summary.income_sources:
            events.append((inc.day_of_month or 1, inc.amount.pence, inc.name))
        for bill in summary.bills:
            if bill.payment_method_id == 1:
                events.append((bill.day_of_month or 28, -bill.amount.pence, bill.name))
        # Income before bills on same day (positive delta sorts first)
        events.sort(key=lambda e: (e[0], -e[1]))

        balance = opening_pence
        min_balance = opening_pence
        min_day = 0
        first_negative_day = None
        rescue_event = None

        for day, delta, name in events:
            balance += delta
            if balance < min_balance:
                min_balance = balance
                min_day = day
            if balance < 0 and first_negative_day is None:
                first_negative_day = day
            if first_negative_day is not None and rescue_event is None and delta > 0 and balance >= 0:
                rescue_event = (day, delta, name)

        closing_pence = balance
        lines = [f"Opens: £{opening_pence / 100:.2f}"]

        if first_negative_day is not None:
            lines.append(
                f"OVERDRAWN by day {first_negative_day}  "
                f"(low: −£{abs(min_balance) / 100:.2f})"
            )
            if rescue_event:
                rday, ramt, rname = rescue_event
                lines.append(f"Rescued day {rday}: {rname} +£{ramt / 100:.2f}")
            else:
                lines.append("No rescue income — remains overdrawn")
        elif min_day and min_balance < monthly_drain_pence:
            lines.append(f"Low point: £{min_balance / 100:.2f} on day {min_day}")

        if closing_pence >= 0:
            lines.append(f"Closes: £{closing_pence / 100:.2f}")
        else:
            lines.append(f"Closes: −£{abs(closing_pence) / 100:.2f}  (still overdrawn)")

        color = self._health_color(min_balance, monthly_drain_pence)
        return "\n".join(lines), color

    @staticmethod
    def _build_card_state_text(cards, bills, opening_balances: dict) -> str:
        """Build per-card balance projection for one month.

        opening_balances: {card_id: pence} — balance at start of this month.
        Returns multi-line text block, empty string if no active cards.
        """
        if not cards:
            return ""
        lines = ["Cards:"]
        for card in cards:
            opening_pence = opening_balances.get(card.id, card.current_balance_used.pence)
            state = calculate_card_monthly_state(
                card=card, opening_balance_pence=opening_pence, bills=list(bills)
            )
            interest_str = (
                f" +£{state.monthly_interest.pounds:.2f} int"
                if state.monthly_interest.pence > 0 else ""
            )
            paid_p = state.payment_received.pence
            min_p = state.minimum_payment.pence
            if paid_p < min_p:
                shortfall_p = min_p - paid_p
                payment_str = (
                    f"paid £{paid_p / 100:.2f} — "
                    f"min £{min_p / 100:.2f} — "
                    f"SHORTFALL £{shortfall_p / 100:.2f}"
                )
            elif paid_p == 0:
                payment_str = f"no payment set (min £{min_p / 100:.2f})"
            else:
                payment_str = f"paid £{paid_p / 100:.2f} (min £{min_p / 100:.2f}) ✓"
            lines.append(
                f"  {card.name}: £{state.opening_balance.pounds:.2f}"
                f"{interest_str} | {payment_str}"
                f" | closes £{state.closing_balance.pounds:.2f}"
            )
        return "\n".join(lines)

    def _simulate_runway(self, starting_balance_pence: int, from_month) -> tuple:
        """Step forward month by month until balance goes negative.

        Returns (overdrawn_month_or_None, months_solvent_count).
        Caps at 24 months to avoid infinite loops on perpetually-solvent scenarios.
        """
        balance = starting_balance_pence
        month = from_month.next_month()
        for i in range(24):
            s = self.view_model.budget_service.get_month_summary(year_month=month)
            bank_bills = sum(b.amount.pence for b in s.bills if b.payment_method_id == 1)
            income = s.total_income.pence
            balance += income - bank_bills
            if balance < 0:
                return month, i + 1
            month = month.next_month()
        return None, 24

    def _rebuild_card_bars(self, report) -> None:
        """Clear and rebuild per-card utilisation bars for the viewed month."""
        while self.card_bars_layout.count():
            item = self.card_bars_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cards = self.view_model.budget_service.get_credit_cards(include_inactive=False)
        if not cards:
            return

        monthly_states = {
            s.card.id: s
            for s in self.view_model.budget_service.get_card_monthly_states(year_month=report.year_month)
        }

        _red_threshold_pence = 10_000    # <= £100 available
        _amber_threshold_pence = 25_000  # <= £250 available

        for card in cards:
            state = monthly_states.get(card.id)
            used_pence = card.current_balance_used.pence
            limit_pence = card.credit_limit.pence
            closing_pence = state.closing_balance.pence if state else used_pence
            available_pence = limit_pence - closing_pence
            util_pct = (used_pence / limit_pence * 100) if limit_pence else 0.0

            name_lbl = QLabel(card.name)
            name_lbl.setStyleSheet(ui_scale.style("font-size: 16px; font-weight: bold; padding-top: 5px;"))
            self.card_bars_layout.addWidget(name_lbl)

            bar = QProgressBar()
            bar.setMaximum(max(1, limit_pence))
            bar.setValue(min(used_pence, limit_pence))
            bar.setMinimumHeight(ui_scale.px(26))
            bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bar.setFormat(
                f"£{used_pence / 100:.2f} of £{limit_pence / 100:.2f} ({util_pct:.1f}%)"
                f"   ·   month-end: £{closing_pence / 100:.2f}"
            )

            if available_pence <= _red_threshold_pence:
                chunk_color = "#f87171"
            elif available_pence <= _amber_threshold_pence:
                chunk_color = "#f59e0b"
            else:
                chunk_color = "#34d399"

            bar.setStyleSheet(
                "QProgressBar { border-radius: 4px; background-color: #1f2937; color: white; font-weight: bold; }"
                f"QProgressBar::chunk {{ background-color: {chunk_color}; border-radius: 4px; }}"
            )
            self.card_bars_layout.addWidget(bar)

            if state:
                delta = closing_pence - used_pence
                arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
                detail = (
                    f"Charges +£{state.charges.pence / 100:.2f}  ·  "
                    f"Payment −£{state.payment_received.pence / 100:.2f}  ·  "
                    f"Interest +£{state.monthly_interest.pence / 100:.2f}  ·  "
                    f"Min due £{state.minimum_payment.pence / 100:.2f}  "
                    f"{arrow} £{abs(delta) / 100:.2f} {'increase' if delta > 0 else 'decrease'}"
                )
                detail_color = "#f87171" if delta > 0 else "#34d399" if delta < 0 else "#9ca3af"
                detail_lbl = QLabel(detail)
                detail_lbl.setStyleSheet(ui_scale.style(f"font-size: 15px; padding: 2px 0px; color: {detail_color};"))
                self.card_bars_layout.addWidget(detail_lbl)

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
                    if b.payment_method_id == 1 and (b.day_of_month or 28) < max_income_day
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

        self._rebuild_card_bars(report)

        m1 = report.year_month.next_month()
        m2 = m1.next_month()
        m1_name = MONTH_NAMES[m1.month]
        m2_name = MONTH_NAMES[m2.month]
        m1_summary = self.view_model.budget_service.get_month_summary(year_month=m1)
        m2_summary = self.view_model.budget_service.get_month_summary(year_month=m2)
        m1_bank = sum(b.amount.pence for b in m1_summary.bills if b.payment_method_id == 1)
        m2_bank = sum(b.amount.pence for b in m2_summary.bills if b.payment_method_id == 1)
        m1_drain = m1_bank - m1_summary.total_income.pence
        m2_drain = m2_bank - m2_summary.total_income.pence
        m1_end_pence = report.balance_pence + m1_summary.total_income.pence - m1_bank

        m1_text, m1_color = self._build_month_cashflow_summary(report.balance_pence, m1_summary, m1_drain)
        m2_text, m2_color = self._build_month_cashflow_summary(m1_end_pence, m2_summary, m2_drain)

        cards = self.view_model.budget_service.get_credit_cards(include_inactive=False)
        m1_card_opening = {c.id: c.current_balance_used.pence for c in cards}
        m1_card_states = {
            c.id: calculate_card_monthly_state(
                card=c, opening_balance_pence=m1_card_opening[c.id], bills=list(m1_summary.bills)
            )
            for c in cards
        }
        m2_card_opening = {c.id: m1_card_states[c.id].closing_balance.pence for c in cards}

        m1_card_text = self._build_card_state_text(cards, m1_summary.bills, m1_card_opening)
        m2_card_text = self._build_card_state_text(cards, m2_summary.bills, m2_card_opening)

        m1_full = f"{m1_name} {m1.year}\n{m1_text}"
        if m1_card_text:
            m1_full += f"\n{m1_card_text}"
        m2_full = f"{m2_name} {m2.year}\n{m2_text}"
        if m2_card_text:
            m2_full += f"\n{m2_card_text}"

        self.m1_projection_label.setText(m1_full)
        self.m1_projection_label.setStyleSheet(ui_scale.style(f"font-size: 17px; padding: 5px; color: {m1_color};"))
        self.m2_projection_label.setText(m2_full)
        self.m2_projection_label.setStyleSheet(ui_scale.style(f"font-size: 17px; padding: 5px; color: {m2_color};"))

        # Month label colour reflects current month's health vs its own upcoming drain
        current_month_color = self._health_color(report.balance_pence, m1_drain)
        self.month_label.setStyleSheet(ui_scale.style(
            f"font-size: 20px; font-weight: bold; padding: 10px; color: {current_month_color};"
        ))
