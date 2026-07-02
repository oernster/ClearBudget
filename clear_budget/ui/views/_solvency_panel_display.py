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
from clear_budget.ui.views._solvency_panel_narratives import _STATE_CAUTION
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
        not_yet_beyond_floor = report.balance_pence >= -overdraft_limit_pence
        if monthly_deficit_pence > 0 and not_yet_beyond_floor:
            overdraft_ym = self.view_model.budget_service.first_overdrawn_month(
                from_year_month=report.year_month,
                from_balance_pence=report.balance_pence,
                overdraft_limit_pence=overdraft_limit_pence,
            )
        overdrawn_next_month = overdraft_ym == next_ym
        deficit_note = self._deficit_note(
            monthly_deficit_pence, overdraft_ym, overdrawn_next_month
        )
        # The banner text spells out the month's situation; its colour and the
        # title-bar colour both come from the shared _state_color classifier, so
        # the only difference is that the banner escalates to red to warn of a
        # next-month overdraft while the title bar reflects the month's own
        # state (see the call below the chain).
        if report.balance_pence < -overdraft_limit_pence:
            beyond_note = (
                f" - beyond your {fmt(overdraft_limit_pence)} overdraft"
                if overdraft_limit_pence > 0
                else facility_alert
            )
            self.overdraft_alert.setText(
                f"CRITICAL: {fmt(abs(balance))} overdrawn{beyond_note}{deficit_note}"
            )
        elif report.balance_pence < 0:
            self.overdraft_alert.setText(
                f"CAUTION: using {fmt(abs(balance))} of your "
                f"{fmt(overdraft_limit_pence)} overdraft{deficit_note}"
            )
        elif overdrawn_next_month:
            self.overdraft_alert.setText(
                f"CRITICAL: overdrawn in {next_month_name} - "
                f"{fmt(balance)} left in savings{facility_alert}{deficit_note}"
            )
        elif monthly_deficit_pence > 0 and balance <= 500:
            self.overdraft_alert.setText(
                f"CRITICAL: projected end of {month_name}: "
                f"{fmt(balance)} - drawing down savings{deficit_note}"
            )
        elif balance <= 200:
            self.overdraft_alert.setText(
                f"AT RISK: only {fmt(balance)} remaining{deficit_note}"
            )
        elif balance <= 500:
            self.overdraft_alert.setText(
                f"CAUTION: {fmt(balance)} remaining{deficit_note}"
            )
        elif monthly_deficit_pence > 0:
            self.overdraft_alert.setText(
                f"CAUTION: {fmt(balance)} after {month_name} bills{deficit_note}"
            )
        else:
            self.overdraft_alert.setText(
                f"SAFE: {fmt(balance)} remaining after all {month_name} bills"
            )
        banner_color = self._state_color(
            report.balance_pence,
            monthly_deficit_pence,
            overdrawn_next_month,
            overdraft_limit_pence,
        )
        # Dark text reads better on the light caution yellow; white elsewhere.
        banner_fg = "#1a1a1a" if banner_color == _STATE_CAUTION else "white"
        self.overdraft_alert.setStyleSheet(
            base_style + f"background-color: {banner_color}; color: {banner_fg};"
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

        # The title-bar colour is the displayed month's OWN within-month health,
        # the same colour Solvency shows for that month: red only when that
        # month's balance actually drops below zero, amber when it dips low or
        # runs at a loss but stays in the black, green when it stays comfortable.
        # It must NOT inherit the banner's next-month overdraft warning: a month
        # that itself never goes negative (e.g. dips to a small positive low)
        # stays amber even while the banner shouts about the month after it.
        current_month_color = self._title_health_color(
            report, is_current_month, overdraft_limit_pence
        )
        apply_nav_label_color(self.month_label, current_month_color)
        # Solvency is the single source of truth for the nav label colour;
        # broadcast it so the other tabs' month/year labels match.
        self.month_label_color_changed.emit(current_month_color)

    def _title_health_color(
        self, report, is_current_month: bool, overdraft_limit_pence: int
    ) -> str:
        """Title-bar colour: the colour Solvency shows for the displayed month.

        For a FUTURE month this is that month's Forward Projection health, from
        the same _build_month_cashflow_summary engine that colours the
        projection rows, so the title matches the paragraph the user saw for
        that month. Red is reserved for breaching the overdraft floor (below
        zero with no facility, or beyond an agreed one); staying positive or
        dipping only within a facility is amber.

        The CURRENT month is judged on its live/actual balance instead. It is
        already underway, so its real trajectory (the Overdraft Status banner's
        own verdict) is what counts, not a re-simulation of the whole month from
        a stale projected opening that would replay already-paid bills and dip
        it spuriously into the red.
        """
        if is_current_month:
            return self._state_color(
                report.balance_pence, 0, False, overdraft_limit_pence
            )
        summary = self.view_model.current_summary
        if not summary:
            return self._health_color(report.balance_pence, 0)
        opening_pence = (
            self.view_model.budget_service.get_projected_starting_balance_pence(
                year_month=report.year_month
            )
        )
        bank_bills_pence = sum(
            b.amount.pence for b in summary.bills if b.payment_method_id == 1
        )
        drain_pence = bank_bills_pence - summary.total_income.pence
        _, color, _ = self._build_month_cashflow_summary(
            opening_pence, summary, drain_pence, overdraft_limit_pence
        )
        return color
