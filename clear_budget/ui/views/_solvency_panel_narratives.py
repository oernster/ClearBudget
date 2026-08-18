"""Narrative-building helpers for SolvencyPanel - extracted for LOC limit."""

from clear_budget.domain.services.card_monthly_calculator import (
    calculate_card_monthly_state,
)
from clear_budget.ui import theme
from clear_budget.ui.theme_tokens import (
    STATE_AT_RISK,
    STATE_CAUTION,
    STATE_RED,
    STATE_SAFE,
)
from clear_budget.ui.utils.format_helpers import fmt

# Balance bands (in pence) separating the amber tiers from a safe close.
_AT_RISK_BALANCE_PENCE = 20000
_CAUTION_BALANCE_PENCE = 50000
# Months of drain a balance must cover to count as comfortable rather than tight.
_MONTHS_COVERAGE_FOR_SAFE = 2
# Sentinel day for a low that sits at the opening balance, before any event.
# Days of the month are 1-based, so 0 cannot collide with a real one.
_LOW_AT_START = 0


class SolvencyPanelNarrativeMixin:
    """Pure(ish) narrative-building helpers used by SolvencyPanel.update_display."""

    @staticmethod
    def _state_color(
        balance_pence: int,
        monthly_deficit_pence: int,
        overdrawn_next_month: bool,
        overdraft_limit_pence: int = 0,
    ) -> str:
        """Traffic-light colour for a month's own solvency state.

        The single source of truth for both the Overdraft Status banner and the
        title-bar label. The red line is the agreed overdraft floor: the balance
        finishing below ``-overdraft_limit_pence`` is red. When no facility is
        defined the floor is zero, so this reduces to red-below-zero. Dipping
        into an agreed facility but staying within it is amber, not red: the
        facility makes it manageable. Red is otherwise reserved for a looming
        next-month overdraft (``overdrawn_next_month``) or a draining month left
        with almost nothing.
        """
        return theme.state_colours()[
            SolvencyPanelNarrativeMixin._state_key(
                balance_pence,
                monthly_deficit_pence,
                overdrawn_next_month,
                overdraft_limit_pence,
            )
        ]

    @staticmethod
    def _state_key(
        balance_pence: int,
        monthly_deficit_pence: int,
        overdrawn_next_month: bool,
        overdraft_limit_pence: int = 0,
    ) -> str:
        """The traffic-light STATE behind _state_color, as a palette key.

        Kept separate so a widget can carry the state itself (the banner sets it
        as a Qt property and lets the theme stylesheet supply the colours) while
        callers that need a colour resolve it through the active palette.
        """
        red_floor_pence = -overdraft_limit_pence
        if balance_pence < red_floor_pence:
            return STATE_RED
        if balance_pence < 0:
            # Into the overdraft but within the agreed facility: a warning.
            return STATE_AT_RISK
        if overdrawn_next_month:
            return STATE_RED
        if monthly_deficit_pence > 0 and balance_pence <= _CAUTION_BALANCE_PENCE:
            return STATE_RED
        if balance_pence <= _AT_RISK_BALANCE_PENCE:
            return STATE_AT_RISK
        if balance_pence <= _CAUTION_BALANCE_PENCE:
            return STATE_CAUTION
        if monthly_deficit_pence > 0:
            return STATE_CAUTION
        return STATE_SAFE

    @staticmethod
    def _health_color(balance_pence: int, monthly_drain_pence: int) -> str:
        """Return traffic-light color based on balance vs monthly drain coverage.

        Red only for actual overdraft (< 0).
        Amber for positive but less than 2 months coverage - tight but surviving.
        Green for 2+ months coverage.
        monthly_drain_pence: bills − income for a future month (positive = deficit).
        """
        states = theme.state_colours()
        if balance_pence < 0:
            return states[STATE_RED]
        if monthly_drain_pence <= 0:
            return states[STATE_SAFE]
        if balance_pence >= _MONTHS_COVERAGE_FOR_SAFE * monthly_drain_pence:
            return states[STATE_SAFE]
        return states[STATE_CAUTION]

    def _build_month_cashflow_summary(
        self,
        opening_pence: int,
        summary,
        monthly_drain_pence: int,
        overdraft_limit_pence: int = 0,
    ) -> tuple[str, str, bool]:
        """Build cashflow risk narrative for one month.

        Simulates events in day order. Returns (display_text, color, clarion).
        ``clarion`` is True when the month goes overdrawn with no facility or
        beyond it, so the caller can render it as a stark warning.
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
        color = self._health_color(min_balance, monthly_drain_pence)
        clarion = False

        # Every month reports its low, whether or not it is alarming: a low
        # shown only when a month is in trouble makes the healthy months look
        # as though they have no low at all, and leaves nothing to compare a
        # worsening month against.
        when = f"on day {min_day}" if min_day != _LOW_AT_START else "at the start"
        if min_balance < 0:
            lines.append(f"Low point: -{fmt(abs(min_balance))} {when}")
        else:
            lines.append(f"Low point: {fmt(min_balance)} {when}")

        if first_negative_day is not None:
            lines.append(f"OVERDRAWN by day {first_negative_day}")
            if rescue_event:
                rday, ramt, rname = rescue_event
                lines.append(f"Rescued day {rday}: {rname} +{fmt(ramt)}")
            else:
                lines.append("No rescue income - remains overdrawn")
            note, color, clarion = self._overdraft_facility_outcome(
                min_balance, overdraft_limit_pence
            )
            lines.append(note)

        if closing_pence >= 0:
            lines.append(f"Closes: {fmt(closing_pence)}")
        else:
            lines.append(f"Closes: -{fmt(abs(closing_pence))}  (still overdrawn)")

        return "\n".join(lines), color, clarion

    @staticmethod
    def _overdraft_facility_outcome(
        min_balance_pence: int, overdraft_limit_pence: int
    ) -> tuple[str, str, bool]:
        """Classify a month's overdraft dip against the agreed facility.

        Returns (note, color, clarion). Within an agreed facility is amber and
        manageable; going overdrawn with no facility or beyond it is a red
        clarion: refused payments and fees.
        """
        if overdraft_limit_pence > 0 and min_balance_pence >= -overdraft_limit_pence:
            return (
                f"Within your {fmt(overdraft_limit_pence)} overdraft facility",
                "#fbbf24",
                False,
            )
        if overdraft_limit_pence > 0:
            over = abs(min_balance_pence) - overdraft_limit_pence
            return (
                f"EXCEEDS your {fmt(overdraft_limit_pence)} overdraft by {fmt(over)}",
                "#f87171",
                True,
            )
        return "NO OVERDRAFT FACILITY - payments would be refused", "#f87171", True

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
        # The low is tracked across EVERY event, not just the income ones that
        # get a line, because a month can be at its worst between two payslips.
        # The opening is a candidate: a month that only ever rises is at its
        # lowest before anything happens, reported as "at the start".
        low_pence = opening_pence
        low_day = _LOW_AT_START
        for day, delta, name, is_income in events:
            balance += delta
            if balance < low_pence:
                low_pence = balance
                low_day = day
            if is_income:
                lines.append(
                    f"Day {day}: {name} +{fmt(delta)} -> balance {fmt(balance)}"
                )
        # Same shape as the forward months' line, so the three months of the
        # page read as one series rather than as three separate reports.
        when = "at the start" if low_day == _LOW_AT_START else f"on day {low_day}"
        if low_pence < 0:
            lines.append(f"Low point: -{fmt(abs(low_pence))} {when}")
        else:
            lines.append(f"Low point: {fmt(low_pence)} {when}")
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
