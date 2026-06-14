"""Solvency panel widget - displays financial health status and warnings."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from clear_budget.domain.services.credit_limit_schedule import (
    month_end_effective_limit_pence,
)
from clear_budget.ui.view_models.solvency_view_model import SolvencyViewModel
from clear_budget.ui.utils.format_helpers import (
    build_centered_nav_header,
    fmt,
    MONTH_NAMES,
)
from clear_budget.ui import ui_scale
from clear_budget.ui.views._solvency_panel_display import SolvencyPanelDisplayMixin
from clear_budget.ui.views._solvency_panel_narratives import (
    SolvencyPanelNarrativeMixin,
)

# The solvency view presents the current month plus the next two (the forward
# projection), so the card bars reflect a committed limit change landing within
# that same three-month outlook, flagged by a pill per transition.
_FORWARD_OUTLOOK_MONTHS = 3


class SolvencyPanel(SolvencyPanelDisplayMixin, SolvencyPanelNarrativeMixin, QWidget):
    """Displays account solvency status with three critical sections."""

    # Broadcasts the health colour applied to the month label so the other tabs'
    # nav labels can match it (Solvency is the single source of truth).
    month_label_color_changed = Signal(str)

    def __init__(self, view_model: SolvencyViewModel, read_only: bool = False) -> None:
        """Initialize solvency panel widget."""
        super().__init__()
        self.view_model = view_model
        self.read_only = read_only
        self.init_ui()
        self.connect_signals()

    def init_ui(self) -> None:
        """Build solvency panel layout with three sections."""
        layout = QVBoxLayout()

        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.next_btn = QPushButton("Next →")
        self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.nav_header, self.month_label = build_centered_nav_header(
            "May 2026", prev_btn=self.prev_btn, next_btn=self.next_btn
        )

        # SECTION 1: OVERDRAFT ALERT (Top - Prominent)
        alert_label = QLabel("Overdraft Status")
        alert_label.setStyleSheet(ui_scale.style("font-weight: bold; font-size: 17px;"))
        layout.addWidget(alert_label)

        self.overdraft_alert = QLabel(f"SAFE: {fmt(0)} buffer")
        self.overdraft_alert.setStyleSheet(
            ui_scale.style(
                "font-size: 22px; font-weight: bold; padding: 10px; border-radius: 5px;"
            )
        )
        layout.addWidget(self.overdraft_alert)

        self.midmonth_alert = QLabel("")
        self.midmonth_alert.setWordWrap(True)
        self.midmonth_alert.setStyleSheet(
            ui_scale.style(
                "font-size: 18px; font-weight: bold; padding: 8px; border-radius: 5px; "
                "background-color: #dc2626; color: white;"
            )
        )
        self.midmonth_alert.hide()
        layout.addWidget(self.midmonth_alert)

        # SECTION 2: OVERALL HEALTH (Middle)
        health_label = QLabel("Overall Health")
        health_label.setStyleSheet(
            ui_scale.style("font-weight: bold; font-size: 17px; margin-top: 20px;")
        )
        layout.addWidget(health_label)

        self.balance_label = QLabel(f"Bank Balance: {fmt(0)}")
        self.balance_label.setStyleSheet(
            ui_scale.style("font-size: 20px; padding: 5px;")
        )
        layout.addWidget(self.balance_label)

        self.committed_label = QLabel("Committed this month: -")
        self.committed_label.setStyleSheet(
            ui_scale.style("font-size: 18px; padding: 5px; color: #9ca3af;")
        )
        layout.addWidget(self.committed_label)

        self.remaining_bank_label = QLabel("Still due this month (bank): -")
        self.remaining_bank_label.setWordWrap(True)
        self.remaining_bank_label.setStyleSheet(
            ui_scale.style("font-size: 18px; padding: 5px; color: #fbbf24;")
        )
        layout.addWidget(self.remaining_bank_label)

        self.remaining_card_label = QLabel("Still due this month (cards): -")
        self.remaining_card_label.setStyleSheet(
            ui_scale.style("font-size: 18px; padding: 5px; color: #f59e0b;")
        )
        layout.addWidget(self.remaining_card_label)

        self.month_breakdown_label = QLabel("")
        self.month_breakdown_label.setWordWrap(True)
        self.month_breakdown_label.setStyleSheet(
            ui_scale.style("font-size: 15px; padding: 5px; color: #9ca3af;")
        )
        layout.addWidget(self.month_breakdown_label)

        cards_header = QLabel("Credit Card Status")
        cards_header.setStyleSheet(
            ui_scale.style("font-weight: bold; font-size: 17px; margin-top: 10px;")
        )
        layout.addWidget(cards_header)

        self.card_bars_container = QWidget()
        self.card_bars_layout = QVBoxLayout(self.card_bars_container)
        self.card_bars_layout.setSpacing(ui_scale.px(3))
        self.card_bars_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.card_bars_container)

        # SECTION 3: FORWARD PROJECTION (Bottom)
        forward_label = QLabel("Forward Projection")
        forward_label.setStyleSheet(
            ui_scale.style("font-weight: bold; font-size: 17px; margin-top: 20px;")
        )
        layout.addWidget(forward_label)

        self.m1_projection_label = QLabel("")
        self.m1_projection_label.setWordWrap(True)
        self.m1_projection_label.setStyleSheet(
            ui_scale.style("font-size: 17px; padding: 5px;")
        )
        layout.addWidget(self.m1_projection_label)

        self.m2_projection_label = QLabel("")
        self.m2_projection_label.setWordWrap(True)
        self.m2_projection_label.setStyleSheet(
            ui_scale.style("font-size: 17px; padding: 5px;")
        )
        layout.addWidget(self.m2_projection_label)

        layout.addStretch()
        self.setLayout(layout)

    def connect_signals(self) -> None:
        """Connect ViewModel signals to view updates."""
        self.view_model.solvency_updated.connect(self.update_display)

    def _simulate_runway(self, starting_balance_pence: int, from_month) -> tuple:
        """Step forward month by month until balance goes negative.

        Returns (overdrawn_month_or_None, months_solvent_count).
        Caps at 24 months to avoid infinite loops on perpetually-solvent scenarios.
        """
        balance = starting_balance_pence
        month = from_month.next_month()
        for i in range(24):
            s = self.view_model.budget_service.get_month_summary(year_month=month)
            bank_bills = sum(
                b.amount.pence for b in s.bills if b.payment_method_id == 1
            )
            income = s.total_income.pence
            balance += income - bank_bills
            if balance < 0:
                return month, i + 1
            month = month.next_month()
        return None, 24

    def _build_limit_change_pills(self, card, displayed, outlook):
        """Build a pill row for the card's scheduled limit changes falling within
        the displayed-to-outlook window (one pill per transition), or None."""
        lo = (displayed.year, displayed.month)
        hi = (outlook.year, outlook.month)
        running = card.credit_limit.pence
        pills = []
        for change in card.scheduled_limit_changes:
            key = (change.effective_year, change.effective_month)
            if lo <= key <= hi:
                increase = change.new_limit.pence >= running
                arrow = "↑" if increase else "↓"
                month_abbr = MONTH_NAMES[change.effective_month][:3]
                pills.append(
                    (
                        f"{arrow} {change.new_limit} · "
                        f"{change.effective_day} {month_abbr}",
                        "#1e3a8a" if increase else "#78350f",
                    )
                )
            running = change.new_limit.pence
        if not pills:
            return None
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(ui_scale.px(6))
        for text, color in pills:
            label = QLabel(text)
            label.setStyleSheet(
                ui_scale.style(
                    "font-size: 11px; font-weight: 600; color: #ffffff;"
                    f" background-color: {color}; border-radius: 4px; padding: 1px 6px;"
                )
            )
            label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            row.addWidget(label)
        row.addStretch(1)
        return container

    def _rebuild_card_bars(self, report) -> None:
        """Clear and rebuild per-card utilisation bars for the viewed month."""
        while self.card_bars_layout.count():
            item = self.card_bars_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cards = self.view_model.budget_service.get_credit_cards(include_inactive=False)
        if not cards:
            return

        # The bar reflects the displayed month's own month-end (below). The pills
        # give the heads-up for changes still ahead within the three-month outlook
        # the page projects (current, next, one after).
        outlook = report.year_month
        for _ in range(_FORWARD_OUTLOOK_MONTHS - 1):
            outlook = outlook.next_month()
        month_name = MONTH_NAMES[report.year_month.month]

        monthly_states = {
            s.card.id: s
            for s in self.view_model.budget_service.get_card_monthly_states(
                year_month=report.year_month
            )
        }

        _red_threshold_pence = 10_000  # <= £100 available
        _amber_threshold_pence = 25_000  # <= £250 available

        for card in cards:
            state = monthly_states.get(card.id)
            used_pence = card.current_balance_used.pence
            # The bar shows the displayed month's own month-end: the projected
            # closing balance against the limit effective by that month's end.
            limit_pence = month_end_effective_limit_pence(
                card=card,
                year=report.year_month.year,
                month=report.year_month.month,
            )
            closing_pence = state.closing_balance.pence if state else used_pence
            available_pence = limit_pence - closing_pence
            util_pct = (closing_pence / limit_pence * 100) if limit_pence else 0.0

            name_lbl = QLabel(card.name)
            name_lbl.setStyleSheet(
                ui_scale.style("font-size: 16px; font-weight: bold; padding-top: 5px;")
            )
            self.card_bars_layout.addWidget(name_lbl)

            bar = QProgressBar()
            bar.setMaximum(max(1, limit_pence))
            bar.setValue(min(closing_pence, limit_pence))
            bar.setMinimumHeight(ui_scale.px(26))
            bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bar.setFormat(
                f"{month_name} month-end: {fmt(closing_pence)}"
                f" of {fmt(limit_pence)} ({util_pct:.1f}%)"
            )

            if available_pence <= _red_threshold_pence:
                chunk_color = "#f87171"
            elif available_pence <= _amber_threshold_pence:
                chunk_color = "#f59e0b"
            else:
                chunk_color = "#34d399"

            bar.setStyleSheet(
                "QProgressBar { border-radius: 4px; background-color: #1f2937;"
                " color: white; font-weight: bold; }"
                f"QProgressBar::chunk {{"
                f" background-color: {chunk_color}; border-radius: 4px; }}"
            )
            self.card_bars_layout.addWidget(bar)

            pills_row = self._build_limit_change_pills(card, report.year_month, outlook)
            if pills_row is not None:
                self.card_bars_layout.addWidget(pills_row)

            if state:
                # Within-month change for the displayed month: closing minus that
                # month's own opening (not today's balance), i.e. the net of this
                # month's charges, payment and interest.
                delta = closing_pence - state.opening_balance.pence
                arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
                detail = (
                    f"Charges +{fmt(state.charges.pence)}  ·  "
                    f"Payment -{fmt(state.payment_received.pence)}  ·  "
                    f"Interest +{fmt(state.monthly_interest.pence)}  ·  "
                    f"Min due {fmt(state.minimum_payment.pence)}  "
                    f"{arrow} {fmt(abs(delta))}"
                    f" {'increase' if delta > 0 else 'decrease'}"
                )
                detail_color = (
                    "#f87171" if delta > 0 else "#34d399" if delta < 0 else "#9ca3af"
                )
                detail_lbl = QLabel(detail)
                detail_lbl.setStyleSheet(
                    ui_scale.style(
                        f"font-size: 15px; padding: 2px 0px; color: {detail_color};"
                    )
                )
                self.card_bars_layout.addWidget(detail_lbl)
