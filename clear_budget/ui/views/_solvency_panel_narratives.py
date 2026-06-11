"""Narrative-building helpers for SolvencyPanel - extracted for LOC limit."""

from clear_budget.domain.services.card_monthly_calculator import (
    calculate_card_monthly_state,
)
from clear_budget.ui.utils.format_helpers import fmt


class SolvencyPanelNarrativeMixin:
    """Pure(ish) narrative-building helpers used by SolvencyPanel.update_display."""

    @staticmethod
    def _health_color(balance_pence: int, monthly_drain_pence: int) -> str:
        """Return traffic-light color based on balance vs monthly drain coverage.

        Red only for actual overdraft (< 0).
        Amber for positive but less than 2 months coverage - tight but surviving.
        Green for 2+ months coverage.
        monthly_drain_pence: bills − income for a future month (positive = deficit).
        """
        if balance_pence < 0:
            return "#f87171"
        if monthly_drain_pence <= 0:
            return "#34d399"
        if balance_pence >= 2 * monthly_drain_pence:
            return "#34d399"
        return "#fbbf24"

    @staticmethod
    def _compute_month_min_balance(opening_pence: int, summary) -> int:
        """Return the minimum bank balance at any point during the month (pence)."""
        events = []
        for inc in summary.income_sources:
            events.append((inc.day_of_month or 1, inc.amount.pence))
        for bill in summary.bills:
            if bill.payment_method_id == 1:
                events.append((bill.day_of_month or 28, -bill.amount.pence))
        events.sort(key=lambda e: (e[0], -e[1]))
        balance = opening_pence
        min_balance = opening_pence
        for _day, delta in events:
            balance += delta
            if balance < min_balance:
                min_balance = balance
        return min_balance

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
            if (
                first_negative_day is not None
                and rescue_event is None
                and delta > 0
                and balance >= 0
            ):
                rescue_event = (day, delta, name)

        closing_pence = balance
        lines = [f"Opens: {fmt(opening_pence)}"]

        if first_negative_day is not None:
            lines.append(
                f"OVERDRAWN by day {first_negative_day}  "
                f"(low: -{fmt(abs(min_balance))})"
            )
            if rescue_event:
                rday, ramt, rname = rescue_event
                lines.append(f"Rescued day {rday}: {rname} +{fmt(ramt)}")
            else:
                lines.append("No rescue income - remains overdrawn")
        elif min_day and min_balance < monthly_drain_pence:
            lines.append(f"Low point: {fmt(min_balance)} on day {min_day}")

        if closing_pence >= 0:
            lines.append(f"Closes: {fmt(closing_pence)}")
        else:
            lines.append(f"Closes: -{fmt(abs(closing_pence))}  (still overdrawn)")

        color = self._health_color(min_balance, monthly_drain_pence)
        return "\n".join(lines), color

    @staticmethod
    def _build_income_timeline(opening_pence: int, income_sources, bills) -> list[str]:
        """Build a chronological line-per-income balance breakdown for the month.

        Bank bill events shift the running balance silently (so the closing
        figure reflects the whole month) but only income events get their own
        line, per the solvency breakdown design.

        ``income_sources`` and ``bills`` must already be filtered to the items
        still outstanding from ``opening_pence`` onward (see
        ``BudgetService.get_remaining_month_items``), otherwise bills already
        paid before today would be subtracted twice.
        """
        events = []
        for inc in income_sources:
            events.append((inc.day_of_month or 1, inc.amount.pence, inc.name, True))
        for bill in bills:
            if bill.payment_method_id == 1:
                events.append(
                    (bill.day_of_month or 28, -bill.amount.pence, bill.name, False)
                )
        events.sort(key=lambda e: (e[0], -e[1]))

        lines = []
        balance = opening_pence
        for day, delta, name, is_income in events:
            balance += delta
            if is_income:
                lines.append(
                    f"Day {day}: {name} +{fmt(delta)} -> balance {fmt(balance)}"
                )
        lines.append(f"Balance at end of month: {fmt(balance)}")
        return lines

    @staticmethod
    def _build_card_state_text(cards, bills, opening_balances: dict) -> str:
        """Build per-card balance projection for one month.

        opening_balances: {card_id: pence} - balance at start of this month.
        Returns multi-line text block, empty string if no active cards.
        """
        if not cards:
            return ""
        lines = ["Cards:"]
        for card in cards:
            opening_pence = opening_balances.get(
                card.id, card.current_balance_used.pence
            )
            state = calculate_card_monthly_state(
                card=card, opening_balance_pence=opening_pence, bills=list(bills)
            )
            interest_str = (
                f" +{fmt(state.monthly_interest.pence)} int"
                if state.monthly_interest.pence > 0
                else ""
            )
            paid_p = state.payment_received.pence
            min_p = state.minimum_payment.pence
            if paid_p < min_p:
                shortfall_p = min_p - paid_p
                payment_str = (
                    f"paid {fmt(paid_p)} - "
                    f"min {fmt(min_p)} - "
                    f"SHORTFALL {fmt(shortfall_p)}"
                )
            elif paid_p == 0:
                payment_str = f"no payment set (min {fmt(min_p)})"
            else:
                payment_str = f"paid {fmt(paid_p)} (min {fmt(min_p)}) ✓"
            lines.append(
                f"  {card.name}: {fmt(state.opening_balance.pence)}"
                f"{interest_str} | {payment_str}"
                f" | closes {fmt(state.closing_balance.pence)}"
            )
        return "\n".join(lines)
