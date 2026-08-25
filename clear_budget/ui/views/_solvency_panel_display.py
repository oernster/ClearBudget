"""Display mixin for SolvencyPanel.update_display - extracted for LOC limit."""

from datetime import date as _date

from clear_budget.domain.services._prorating import (
    days_in_month,
    prorate_remaining_pence,
)
from clear_budget.ui import theme, ui_scale
from clear_budget.ui.label_roles import set_role as _repolish_role
from clear_budget.ui.theme_tokens import STATE_RED, STATE_SAFE
from clear_budget.ui.utils import reserves_text
from clear_budget.ui.utils.format_helpers import (
    MONTH_NAMES,
    fmt,
)


def _repolish(widget) -> None:
    """Re-resolve `widget`'s stylesheet after a state property change."""
    _repolish_role(widget, widget.objectName())


class SolvencyPanelDisplayMixin:
    """update_display logic for SolvencyPanel."""

    def _deficit_note(
        self, monthly_deficit_pence: int, overdraft_ym, overdrawn_next_month: bool
    ) -> str:
        """Parenthetical runway note for a deficit month.

        States the monthly drain and also names the month a future overdraft
        first lands in when that is further out than next month (a mid-month dip
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

    def restyle(self) -> None:
        """Re-render after a theme switch, so code-set colours follow it."""
        if getattr(self, "_last_report", None) is not None:
            self.update_display(self._last_report)

    def update_display(self, report) -> None:
        if not report:
            return
        self._last_report = report
        self._update_safe_to_spend()

        month_name = MONTH_NAMES[report.year_month.month]
        self.month_label.setText(f"{month_name} {report.year_month.year}")

        balance = report.balance_pence / 100
        today = _date.today()  # noqa: DTZ011 (local date)
        is_current_month = (
            report.year_month.year == today.year
            and report.year_month.month == today.month
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
        # Sentence case, not capitals. The fact still has to be stated, since
        # going under with nothing arranged means a payment bounces rather
        # than drawing on a facility. The "Critical" prefix already carries
        # the alarm; shouting it a second time only made the line harder to
        # read. "arranged" rather than "facility" because that is the word a
        # bank uses when you ask for one.
        facility_alert = (
            ", with no overdraft arranged" if overdraft_limit_pence == 0 else ""
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
        # State prefixes are sentence case ("Critical:", not "CRITICAL:").
        # They still lead every line, because the word is what carries the
        # state for a reader who does not take it from the banner's colour,
        # so it must not be dropped. Capitals added nothing that the word and
        # the fill were not already saying; a line opening in shouting capitals
        # is read as an alarm even in the Safe case, which is the one state
        # that should read calmly. The palette key underneath is
        # untouched, so the colours and the stylesheet are unaffected.
        #
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
            self.position_banner.setText(
                f"Critical: {fmt(abs(balance))} overdrawn{beyond_note}{deficit_note}"
            )
        elif report.balance_pence < 0:
            self.position_banner.setText(
                f"Caution: using {fmt(abs(balance))} of your "
                f"{fmt(overdraft_limit_pence)} overdraft{deficit_note}"
            )
        elif overdrawn_next_month:
            self.position_banner.setText(
                f"Critical: overdrawn in {next_month_name} - "
                f"{fmt(balance)} left in savings{facility_alert}{deficit_note}"
            )
        elif monthly_deficit_pence > 0 and balance <= 500:
            self.position_banner.setText(
                f"Critical: projected end of {month_name}: "
                f"{fmt(balance)} - drawing down savings{deficit_note}"
            )
        elif balance <= 200:
            self.position_banner.setText(
                f"At risk: only {fmt(balance)} remaining{deficit_note}"
            )
        elif balance <= 500:
            self.position_banner.setText(
                f"Caution: {fmt(balance)} remaining{deficit_note}"
            )
        elif monthly_deficit_pence > 0:
            self.position_banner.setText(
                f"Caution: {fmt(balance)} after {month_name} bills{deficit_note}"
            )
        else:
            self.position_banner.setText(
                f"Safe: {fmt(balance)} remaining after all {month_name} bills"
            )
        # The banner carries its state, not a colour: the theme stylesheet
        # supplies the fill, so it follows a light/dark switch on its own.
        states = theme.state_colours()
        self.position_banner.setProperty(
            "state",
            self._state_key(
                report.balance_pence,
                monthly_deficit_pence,
                overdrawn_next_month,
                overdraft_limit_pence,
            ),
        )
        _repolish(self.position_banner)

        # The dip and its wording live in _solvency_panel_midmonth, which also
        # explains why the line reads its state against the agreed overdraft
        # floor rather than against zero.
        self.midmonth_alert.hide()
        dip = (
            self._midmonth_dip(report, summary)
            if not is_current_month and summary
            else None
        )
        if dip is not None:
            shortfall_pence, income_day = dip
            text, state = self._midmonth_alert_text(
                shortfall_pence, income_day, overdraft_limit_pence
            )
            self.midmonth_alert.setText(text)
            self.midmonth_alert.setProperty("state", state)
            _repolish(self.midmonth_alert)
            self.midmonth_alert.show()

        self.balance_label.setText(f"Projected Balance: {fmt(balance)}")
        self._update_set_aside(report.year_month)

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
                    ui_scale.style(
                        "font-size: 18px; padding: 5px;"
                        f" color: {theme.colours()['warn']};"
                    )
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
                net_color = states[STATE_RED] if net_pence > 0 else states[STATE_SAFE]
                # The projected end is the bottom line, so colour it by its own
                # sign (green while still in the black) rather than inheriting the
                # red from the bills-vs-income deficit that drives the line above.
                end_color = (
                    states[STATE_RED]
                    if report.balance_pence < 0
                    else states[STATE_SAFE]
                )
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

        self._update_month_gap(report.year_month)
        self._update_assumed(report)
        self._render_forward_projection(report, overdraft_limit_pence, is_current_month)

    def _update_set_aside(self, year_month) -> None:
        """What the viewed month has to put by, beside what it has committed.

        A whole-month figure like the gap below it, read as at the month's
        first day, so it states what a month like this costs rather than what
        is being held at this moment. The Reserves page answers that second
        question and this line would contradict it if it tried to.

        Hidden entirely while nothing is set aside, so a budget that never
        opens the Reserves page keeps the breakdown it has always had.
        """
        service = self.view_model.budget_service
        if not service.list_commitments():
            self.set_aside_label.hide()
            return
        cost = service.get_month_reserve_cost_pence(year_month=year_month)
        self.set_aside_label.setText(
            reserves_text.solvency_set_aside_line(amount=fmt(cost))
        )
        self.set_aside_label.show()

    def _update_month_gap(self, year_month) -> None:
        """State what the month needs to hold flat and what its cards cost.

        Shown for EVERY month including the one in progress. The banner's
        runway note is deliberately future-months-only, because it is about
        savings draining from here; this is a different question, about the
        shape of the month itself; the answer does not change as the
        month elapses. It is the figure that turns "this month does not hold
        together" into something with a size.

        The two lines are never added together. The gap is the bank
        account's; the interest accrues on the cards and never leaves the
        bank, so a combined total would claim money that was never going to
        move.
        """
        gap = self.view_model.budget_service.get_month_gap(year_month=year_month)
        month_name = MONTH_NAMES[year_month.month]
        self.gap_label.setText(f"{month_name} {self._gap_clause(gap.needed_pence)}")

    def _title_health_color(
        self, report, is_current_month: bool, overdraft_limit_pence: int
    ) -> str:
        """Title-bar colour: the colour Solvency shows for the displayed month.

        For a FUTURE month this is that month's Forward Projection health, from
        the same _build_month_cashflow_summary engine that colours the
        projection rows, so the title matches the paragraph the user saw for
        that month. Red is reserved for breaching the overdraft floor (below
        zero with no facility or beyond an agreed one); staying positive or
        dipping only within a facility is amber.

        The CURRENT month is judged on its live/actual balance instead. It is
        already underway, so its real trajectory (the Account Position banner's
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
