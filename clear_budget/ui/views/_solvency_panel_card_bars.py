"""Credit-card utilisation bars for SolvencyPanel.

Extracted from solvency_panel to keep that module under the 400-LOC limit
(tests/structural/test_loc_limits.py). Owns one concern: the per-card bar
block under Credit Card Status, its scheduled-limit-change pills and the
within-month movement line beneath each bar.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QWidget,
)

from clear_budget.domain.services.credit_limit_schedule import (
    month_end_effective_limit_pence,
)
from clear_budget.ui import theme, ui_scale
from clear_budget.ui.theme_tokens import STATE_AT_RISK, STATE_RED, STATE_SAFE
from clear_budget.ui.utils.format_helpers import MONTH_NAMES, fmt, percentage
from clear_budget.ui.utils.text_metrics import comfortable_row_height

# The solvency view presents the current month plus the next two (the forward
# projection), so the card bars reflect a committed limit change landing within
# that same three-month outlook, flagged by a pill per transition.
_FORWARD_OUTLOOK_MONTHS = 3


class SolvencyPanelCardBarsMixin:
    """Renders the per-card utilisation bars under Credit Card Status."""

    def _build_limit_change_pills(self, card, displayed, outlook):
        """Build a pill row for the card's scheduled limit changes falling within
        the displayed-to-outlook window (one pill per transition) or None."""
        lo = (displayed.year, displayed.month)
        hi = (outlook.year, outlook.month)
        running = card.credit_limit.pence
        colours = theme.colours()
        pills = []
        for change in card.scheduled_limit_changes:
            key = (change.effective_year, change.effective_month)
            if lo <= key <= hi:
                increase = change.new_limit.pence >= running
                arrow = "↑" if increase else "↓"
                month_abbr = MONTH_NAMES[change.effective_month][:3]
                label = (
                    f"{arrow} {change.new_limit} · "
                    f"{change.effective_day} {month_abbr}"
                )
                pills.append(
                    (
                        label,
                        colours["pill_up_bg"] if increase else colours["pill_down_bg"],
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
                    "font-size: 11px; font-weight: 600;"
                    f" color: {colours['primary_text']};"
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
            # The bar draws its text centred inside itself, so its floor is
            # the same line box a table row needs, not a guessed number.
            bar.setMinimumHeight(comfortable_row_height(bar))
            bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bar.setFormat(
                f"{month_name} month-end: {fmt(closing_pence)}"
                f" of {fmt(limit_pence)} ({percentage(util_pct)})"
            )

            colours = theme.colours()
            states = theme.state_colours()
            if available_pence <= _red_threshold_pence:
                chunk_color = states[STATE_RED]
            elif available_pence <= _amber_threshold_pence:
                chunk_color = states[STATE_AT_RISK]
            else:
                chunk_color = states[STATE_SAFE]

            bar.setStyleSheet(
                "QProgressBar { border-radius: 4px;"
                f" background-color: {colours['card_stat_bg']};"
                f" color: {colours['bar_text']}; font-weight: bold; }}"
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
