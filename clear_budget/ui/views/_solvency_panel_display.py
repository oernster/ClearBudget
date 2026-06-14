"""Display mixin for SolvencyPanel.update_display - extracted for LOC limit."""

from datetime import date as _date

from clear_budget.domain.services._card_live_projection import (
    anchored_month_opening_pence,
)
from clear_budget.domain.services.card_monthly_calculator import (
    calculate_card_monthly_state,
)
from clear_budget.domain.services._prorating import (
    days_in_month,
    prorate_remaining_pence,
)
from clear_budget.ui.utils.format_helpers import (
    MONTH_NAMES,
    apply_nav_label_color,
    fmt,
)
from clear_budget.ui import ui_scale


class SolvencyPanelDisplayMixin:
    """update_display logic for SolvencyPanel."""

    def _deficit_note(
        self, monthly_deficit_pence: int, overdraft_ym, overdrawn_next_month: bool
    ) -> str:
        """Parenthetical runway note for a deficit month.

        States the monthly drain and, when a future overdraft lands further out
        than next month, the month it first dips into one (a mid-month dip
        counts even if later income lifts the close back positive). A next-month
        dip is named by the banner itself, so it is omitted here. Empty when
        income covers the bills.
        """
        if monthly_deficit_pence <= 0:
            return ""
        parts = [f"savings falling {fmt(monthly_deficit_pence)}/month"]
        if overdraft_ym is not None and not overdrawn_next_month:
            parts.append(
                f"overdrawn by {MONTH_NAMES[overdraft_ym.month]} "
                f"{overdraft_ym.year}"
            )
        return " (" + ", ".join(parts) + ")"

    def update_display(self, report) -> None:
        if not report:
            return

        month_name = MONTH_NAMES[report.year_month.month]
        self.month_label.setText(f"{month_name} {report.year_month.year}")

        balance = report.balance_pence / 100
        today = _date.today()
        is_current_month = (
            report.year_month.year == today.year
            and report.year_month.month == today.month
        )
        base_style = ui_scale.style(
            "font-size: 22px; font-weight: bold; padding: 10px; border-radius: 5px; "
        )
        summary = self.view_model.current_summary
        monthly_deficit_pence = 0
        if not is_current_month and summary:
            bank_bills = sum(
                b.amount.pence for b in summary.bills if b.payment_method_id == 1
            )
            monthly_deficit_pence = bank_bills - summary.total_income.pence

        overdraft_limit_pence = (
            self.view_model.budget_service.get_overdraft_limit().pence
        )
        facility_alert = (
            " - NO OVERDRAFT FACILITY" if overdraft_limit_pence == 0 else ""
        )
        next_ym = report.year_month.next_month()
        next_month_name = MONTH_NAMES[next_ym.month]
        # First future month that dips into the red (a mid-month dip counts),
        # used both to escalate when it is the very next month and to state the
        # runway. Same intra-month basis as the forward projection below.
        overdraft_ym = None
        if monthly_deficit_pence > 0 and report.balance_pence >= 0:
            overdraft_ym = self.view_model.budget_service.first_overdrawn_month(
                from_year_month=report.year_month,
                from_balance_pence=report.balance_pence,
            )
        overdrawn_next_month = overdraft_ym == next_ym
        deficit_note = self._deficit_note(
            monthly_deficit_pence, overdraft_ym, overdrawn_next_month
        )
        if balance < 0:
            self.overdraft_alert.setText(
                f"CRITICAL: {fmt(abs(balance))} overdrawn{facility_alert}{deficit_note}"
            )
            self.overdraft_alert.setStyleSheet(
                base_style + "background-color: #f87171; color: white;"
            )
        elif overdrawn_next_month:
            self.overdraft_alert.setText(
                f"CRITICAL: overdrawn in {next_month_name} - "
                f"{fmt(balance)} left in savings{facility_alert}{deficit_note}"
            )
            self.overdraft_alert.setStyleSheet(
                base_style + "background-color: #f87171; color: white;"
            )
        elif monthly_deficit_pence > 0 and balance <= 500:
            self.overdraft_alert.setText(
                f"CRITICAL: projected end of {month_name}: "
                f"{fmt(balance)} - drawing down savings{deficit_note}"
            )
            self.overdraft_alert.setStyleSheet(
                base_style + "background-color: #f87171; color: white;"
            )
        elif balance <= 200:
            self.overdraft_alert.setText(
                f"AT RISK: only {fmt(balance)} remaining{deficit_note}"
            )
            self.overdraft_alert.setStyleSheet(
                base_style + "background-color: #f59e0b; color: white;"
            )
        elif balance <= 500:
            self.overdraft_alert.setText(
                f"CAUTION: {fmt(balance)} remaining{deficit_note}"
            )
            self.overdraft_alert.setStyleSheet(
                base_style + "background-color: #fbbf24; color: #1a1a1a;"
            )
        elif monthly_deficit_pence > 0:
            self.overdraft_alert.setText(
                f"CAUTION: {fmt(balance)} after {month_name} bills{deficit_note}"
            )
            self.overdraft_alert.setStyleSheet(
                base_style + "background-color: #fbbf24; color: #1a1a1a;"
            )
        else:
            self.overdraft_alert.setText(
                f"SAFE: {fmt(balance)} remaining after all {month_name} bills"
            )
            self.overdraft_alert.setStyleSheet(
                base_style + "background-color: #34d399; color: white;"
            )

        self.midmonth_alert.hide()
        if not is_current_month and summary and summary.income_sources:
            income_days = [
                (i.day_of_month or 1, i.amount.pence) for i in summary.income_sources
            ]
            max_income_day = max(d for d, _ in income_days)
            if max_income_day > 1:
                starting_pence = (
                    report.balance_pence
                    - summary.total_income.pence
                    + summary.bank_bills.pence
                )
                early_income = sum(
                    amt for day, amt in income_days if day < max_income_day
                )
                early_bills = sum(
                    b.amount.pence
                    for b in summary.bills
                    if b.payment_method_id == 1
                    and (b.day_of_month or 28) < max_income_day
                )
                mid_balance = starting_pence + early_income - early_bills
                if mid_balance < 0:
                    self.midmonth_alert.setText(
                        f"CRITICAL: overdrawn {fmt(abs(mid_balance))} "
                        f"before day-{max_income_day} income"
                        f" - rescued day {max_income_day}{facility_alert}"
                    )
                    self.midmonth_alert.show()

        self.balance_label.setText(f"Projected Balance: {fmt(balance)}")

        if summary:
            if is_current_month:
                committed = sum(
                    b.amount.pence
                    for b in summary.bills
                    if b.day_of_month and b.day_of_month < today.day
                )
                total_days = days_in_month(today.year, today.month)
                remaining_bank = sum(
                    (
                        prorate_remaining_pence(b.amount.pence, today.day, total_days)
                        if not b.day_of_month
                        else b.amount.pence
                    )
                    for b in summary.bills
                    if (not b.day_of_month or b.day_of_month >= today.day)
                    and b.payment_method_id == 1
                    and not b.paid_for_month
                )
                remaining_card = sum(
                    (
                        prorate_remaining_pence(b.amount.pence, today.day, total_days)
                        if not b.day_of_month
                        else b.amount.pence
                    )
                    for b in summary.bills
                    if (not b.day_of_month or b.day_of_month >= today.day)
                    and b.payment_method_id != 1
                    and not b.paid_for_month
                )
                self.committed_label.setText(f"Committed this month: {fmt(committed)}")
                self.remaining_bank_label.setStyleSheet(
                    ui_scale.style("font-size: 18px; padding: 5px; color: #fbbf24;")
                )
                self.remaining_bank_label.setText(
                    f"Still due this month (bank): {fmt(remaining_bank)}"
                )
                self.remaining_card_label.setText(
                    f"Still due this month (cards): {fmt(remaining_card)}"
                )
            else:
                all_bank = sum(
                    b.amount.pence for b in summary.bills if b.payment_method_id == 1
                )
                all_card = sum(
                    b.amount.pence for b in summary.bills if b.payment_method_id != 1
                )
                income_pence = summary.total_income.pence
                net_pence = all_bank - income_pence
                self.committed_label.setText("Committed this month: -")
                net_color = "#f87171" if net_pence > 0 else "#34d399"
                # The projected end is the bottom line, so colour it by its own
                # sign (green while still in the black) rather than inheriting the
                # red from the bills-vs-income deficit that drives the line above.
                end_color = "#f87171" if report.balance_pence < 0 else "#34d399"
                self.remaining_bank_label.setText(
                    f"<span style='color:{net_color};'>Bank bills: {fmt(all_bank)}"
                    f" vs income {fmt(income_pence)}</span><br>"
                    f"<span style='color:{end_color};'>💰 projected end:"
                    f" {fmt(balance)}</span>"
                )
                self.remaining_bank_label.setStyleSheet(
                    ui_scale.style("font-size: 18px; padding: 5px;")
                )
                self.remaining_card_label.setText(
                    f"All bills this month (cards): {fmt(all_card)}"
                )
        else:
            self.committed_label.setText("Committed this month: -")
            self.remaining_bank_label.setText("Still due this month (bank): -")
            self.remaining_card_label.setText("Still due this month (cards): -")

        if summary and summary.income_sources:
            opening_pence = (
                self.view_model.budget_service.get_projected_starting_balance_pence(
                    year_month=report.year_month
                )
            )
            remaining_bills, remaining_income = (
                self.view_model.budget_service.get_remaining_month_items(
                    year_month=report.year_month, summary=summary
                )
            )
            timeline_lines = self._build_income_timeline(
                opening_pence, remaining_income, remaining_bills
            )
            self.month_breakdown_label.setText(
                f"{month_name} balance breakdown:\n" + "\n".join(timeline_lines)
            )
        else:
            self.month_breakdown_label.setText("")

        # Compute M1/M2 forward data needed for projections.
        m1 = report.year_month.next_month()
        m2 = m1.next_month()
        m1_name = MONTH_NAMES[m1.month]
        m2_name = MONTH_NAMES[m2.month]
        m1_summary = self.view_model.budget_service.get_month_summary(year_month=m1)
        m2_summary = self.view_model.budget_service.get_month_summary(year_month=m2)
        m1_bank = sum(
            b.amount.pence for b in m1_summary.bills if b.payment_method_id == 1
        )
        m2_bank = sum(
            b.amount.pence for b in m2_summary.bills if b.payment_method_id == 1
        )
        m1_drain = m1_bank - m1_summary.total_income.pence
        m2_drain = m2_bank - m2_summary.total_income.pence
        m1_end_pence = report.balance_pence + m1_summary.total_income.pence - m1_bank

        self._rebuild_card_bars(report)

        m1_text, m1_color, m1_clarion = self._build_month_cashflow_summary(
            report.balance_pence, m1_summary, m1_drain, overdraft_limit_pence
        )
        m2_text, m2_color, m2_clarion = self._build_month_cashflow_summary(
            m1_end_pence, m2_summary, m2_drain, overdraft_limit_pence
        )

        cards = self.view_model.budget_service.get_credit_cards(include_inactive=False)
        m1_card_opening = {
            c.id: anchored_month_opening_pence(
                card=c, bills=list(m1_summary.bills), year=m1.year, month=m1.month
            )
            for c in cards
        }
        m1_card_states = {
            c.id: calculate_card_monthly_state(
                card=c,
                opening_balance_pence=m1_card_opening[c.id],
                bills=list(m1_summary.bills),
            )
            for c in cards
        }
        m2_card_opening = {
            c.id: m1_card_states[c.id].closing_balance.pence for c in cards
        }

        m1_card_text = self._build_card_state_text(
            cards, m1_summary.bills, m1_card_opening
        )
        m2_card_text = self._build_card_state_text(
            cards, m2_summary.bills, m2_card_opening
        )

        m1_full = f"{m1_name} {m1.year}\n{m1_text}"
        if m1_card_text:
            m1_full += f"\n{m1_card_text}"
        m2_full = f"{m2_name} {m2.year}\n{m2_text}"
        if m2_card_text:
            m2_full += f"\n{m2_card_text}"

        m1_style = f"font-size: 17px; padding: 5px; color: {m1_color};"
        if m1_clarion:
            m1_style += " font-weight: bold; font-style: italic;"
        self.m1_projection_label.setText(m1_full)
        self.m1_projection_label.setStyleSheet(ui_scale.style(m1_style))
        m2_style = f"font-size: 17px; padding: 5px; color: {m2_color};"
        if m2_clarion:
            m2_style += " font-weight: bold; font-style: italic;"
        self.m2_projection_label.setText(m2_full)
        self.m2_projection_label.setStyleSheet(ui_scale.style(m2_style))

        current_month_color = self._health_color(report.balance_pence, m1_drain)
        apply_nav_label_color(self.month_label, current_month_color)
        # Solvency is the single source of truth for the nav label colour;
        # broadcast it so the other tabs' month/year labels match.
        self.month_label_color_changed.emit(current_month_color)
