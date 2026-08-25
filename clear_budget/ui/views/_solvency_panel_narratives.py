"""Narrative-building helpers for SolvencyPanel - extracted for LOC limit."""

from clear_budget.application.services._month_walk import (
    LOW_AT_START,
    walk_month,
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
# Months of shortfall a balance must cover to count as comfortable rather
# than tight.
_MONTHS_COVERAGE_FOR_SAFE = 2
# Sentinel day for a low that sits at the opening balance, before any event.
# Days of the month are 1-based, so 0 cannot collide with a real one.
# Re-exported from the walk that owns it, so the two cannot drift.
_LOW_AT_START = LOW_AT_START


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

        The single source of truth for both the Account Position banner and the
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
    def _bank_total(summary) -> int:
        """Total pence of a month's bills paid from the bank account."""
        return sum(b.amount.pence for b in summary.bills if b.payment_method_id == 1)

    def _month_shortfall_pence(self, year_month, summary) -> int:
        """What a month has to find: its bank bills and its reserves, less income.

        The ONE place this is worked out. It was derived separately at four
        call sites, which is how the Forward Projection came to say a month
        paid for itself while the Overall Health line above it said that same
        month was short: one sentence, two different sums behind it.

        Emphatically NOT the fall in the balance. Money set aside stays in the
        account until the commitment is paid, so a projected balance must
        never be reduced by it; the Account Position banner's savings-drain
        note is a different figure for that reason and keeps the bills alone.
        This answers what the month must FIND, which is the question the
        health rule and the gap clause both ask.
        """
        reserve = self.view_model.budget_service.get_month_reserve_cost_pence(
            year_month=year_month
        )
        return self._bank_total(summary) + reserve - summary.total_income.pence

    @staticmethod
    def _health_state_key(balance_pence: int, monthly_shortfall_pence: int) -> str:
        """The traffic-light STATE of a month, balance against what it must find.

        Red only for actual overdraft (< 0).
        Amber for positive but less than 2 months coverage - tight but surviving.
        Green for 2+ months coverage.
        monthly_shortfall_pence: what the month has to find, its bank bills and
        its reserves against its income (positive = short). A month that cannot
        fund what it sets aside is genuinely tighter than the bills alone say,
        so the reserve belongs in the figure the coverage is measured against.

        Kept separate from the colour for the same reason _state_key is: the
        projection page paints the same months in the muted assumed variant of
        their own state, so it needs the state rather than a resolved colour.
        """
        if balance_pence < 0:
            return STATE_RED
        if monthly_shortfall_pence <= 0:
            return STATE_SAFE
        if balance_pence >= _MONTHS_COVERAGE_FOR_SAFE * monthly_shortfall_pence:
            return STATE_SAFE
        return STATE_CAUTION

    @staticmethod
    def _health_color(balance_pence: int, monthly_shortfall_pence: int) -> str:
        """_health_state_key resolved through the active theme's palette."""
        return theme.state_colours()[
            SolvencyPanelNarrativeMixin._health_state_key(
                balance_pence, monthly_shortfall_pence
            )
        ]

    @staticmethod
    def _walk_month(opening_pence: int, summary) -> dict:
        """The month's simulation, now owned by the application layer.

        Kept as a method because every caller here reads it through `self`;
        also because the Reserves page must read the SAME walk: two pages
        agreeing about a month is a property of there being one simulation,
        never of two being written carefully.
        """
        return walk_month(opening_pence, summary)

    def _build_month_cashflow_summary(
        self,
        opening_pence: int,
        summary,
        monthly_shortfall_pence: int,
        overdraft_limit_pence: int = 0,
    ) -> tuple[str, str, bool]:
        """Build cashflow risk narrative for one month.

        Simulates events in day order. Returns (display_text, color, clarion).
        ``clarion`` is True when the month goes overdrawn with no facility or
        beyond it, so the caller can render it as a stark warning.
        monthly_shortfall_pence is what the month has to find, its bills and
        its reserves against its income: it picks the amber/red thresholds AND
        is stated outright as what the month needs to hold flat. It is NOT the
        fall in the balance, which the walk works out for itself; see
        _month_shortfall_pence.
        """
        walk = self._walk_month(opening_pence, summary)
        min_balance = walk["min_balance"]
        min_day = walk["min_day"]
        first_negative_day = walk["first_negative_day"]
        rescue_event = walk["rescue_event"]
        closing_pence = walk["closing"]
        lines = [f"Opens: {fmt(opening_pence)}"]
        state = self._health_state_key(min_balance, monthly_shortfall_pence)
        clarion = False

        # Every month reports its low, whether or not it is alarming: a low
        # shown only when a month is in trouble makes the healthy months look
        # as though they have no low at all; it also leaves nothing to compare
        # a worsening month against.
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
            note, state, clarion = self._overdraft_facility_outcome(
                min_balance, overdraft_limit_pence
            )
            lines.append(note)

        if closing_pence >= 0:
            lines.append(f"Closes: {fmt(closing_pence)}")
        else:
            lines.append(f"Closes: -{fmt(abs(closing_pence))}  (still overdrawn)")

        # Every month states its shape, on the same terms as the month on
        # screen. A month that closes positive can still run at a loss; that
        # is precisely the case a closing balance alone hides.
        clause = self._gap_clause(monthly_shortfall_pence)
        lines.append(clause[0].upper() + clause[1:])

        return "\n".join(lines), theme.state_colours()[state], clarion

    def _month_cashflow_state(
        self,
        opening_pence: int,
        summary,
        monthly_shortfall_pence: int,
        overdraft_limit_pence: int = 0,
    ) -> str:
        """The state key behind _build_month_cashflow_summary's colour.

        Reads the same walk through the same two classifiers, so the muted
        rendering on the projection page can never disagree with the full one
        about what state a month is in.
        """
        walk = self._walk_month(opening_pence, summary)
        if walk["first_negative_day"] is not None:
            return self._overdraft_facility_outcome(
                walk["min_balance"], overdraft_limit_pence
            )[1]
        return self._health_state_key(walk["min_balance"], monthly_shortfall_pence)

    @staticmethod
    def _overdraft_facility_outcome(
        min_balance_pence: int, overdraft_limit_pence: int
    ) -> tuple[str, str, bool]:
        """Classify a month's overdraft dip against the agreed facility.

        Returns (note, state_key, clarion). Within an agreed facility is amber
        and manageable; going overdrawn with no facility or beyond it is a red
        clarion: refused payments and fees. The state is a palette key rather
        than a colour so both themes and both readings resolve it themselves.
        """
        if overdraft_limit_pence > 0 and min_balance_pence >= -overdraft_limit_pence:
            return (
                f"Within your {fmt(overdraft_limit_pence)} overdraft facility",
                STATE_CAUTION,
                False,
            )
        if overdraft_limit_pence > 0:
            over = abs(min_balance_pence) - overdraft_limit_pence
            return (
                f"EXCEEDS your {fmt(overdraft_limit_pence)} overdraft by {fmt(over)}",
                STATE_RED,
                True,
            )
        return "NO OVERDRAFT FACILITY - payments would be refused", STATE_RED, True

    @staticmethod
    def _gap_clause(needed_pence: int) -> str:
        """One month's shape as a clause: what it needs or what it spares.

        Shared by the Overall Health line and by every Forward Projection
        block so the wording and the sign convention cannot drift apart. Each
        caller supplies its own subject, since one sits under a month heading
        already and the other does not.
        """
        if needed_pence > 0:
            return f"needs {fmt(needed_pence)} more to hold flat"
        if needed_pence < 0:
            return f"pays for itself, {fmt(abs(needed_pence))} to spare"
        return "pays for itself exactly"

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
