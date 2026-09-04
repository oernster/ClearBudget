"""How one forecast month states its verdict: the figure, the deadline, the shape.

Split from `_solvency_panel_narratives` for the module size limit
(`tests/structural/test_loc_limits.py`), which is why it exists as a file. It
is one concern rather than an arbitrary slice: everything here turns a walked
month into the two lines the Forward Projection prints for it, plus the
classification of a dip against an arranged overdraft that decides how those
lines are painted. The classifiers for the banner and the title bar, the
hold-flat gap and the displayed month's own timeline stayed behind, because
they answer different questions on different surfaces.

`SolvencyPanelNarrativeMixin` inherits this, so every call site still reaches
these through `self` and nothing moved for a caller.
"""

from clear_budget.domain.value_objects.month_afloat import MonthAfloat
from clear_budget.ui.theme_tokens import STATE_CAUTION, STATE_RED
from clear_budget.ui.utils.format_helpers import fmt

# Sentinel day for a low (or a breach) that sits at the opening balance before
# any event. Days are 1-based, so 0 cannot collide with a real one.
from clear_budget.application.services._month_walk import LOW_AT_START

_LOW_AT_START = LOW_AT_START


class SolvencyPanelMonthLinesMixin:
    """The wording of one forecast month's verdict."""

    @staticmethod
    def _signed(pence: int) -> str:
        """A pence figure with its sign, since fmt reports the magnitude."""
        return f"-{fmt(abs(pence))}" if pence < 0 else fmt(pence)

    @staticmethod
    def _shape_line(opening_pence: int, walk: dict) -> str:
        """Where the month starts, where it dips and where it ends, on one line.

        Every month gets it, in trouble or not: a shape shown only for a month
        in difficulty makes the healthy months look as though they have none
        and leaves nothing to compare a worsening month against. One line
        rather than three, because it is the evidence behind the figure above
        it rather than a second reading in its own right.

        The low's DAY is here while its amount is not: the amount is the
        figure on the line above, so printing it twice was what made the block
        read as a warning repeating itself.
        """
        when = (
            "at the start"
            if walk["min_day"] == _LOW_AT_START
            else f"day {walk['min_day']}"
        )
        return (
            f"Opens {fmt(opening_pence)}, lowest {when}, "
            f"closes {SolvencyPanelMonthLinesMixin._signed(walk['closing'])}"
        )

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
    def _afloat_clause(
        low_point_pence: int,
        overdraft_limit_pence: int,
        breach_day: int | None = None,
    ) -> str:
        """One month's rescue figure as a clause: how much; by when.

        AN AMOUNT WITH NO DEADLINE IS NOT ACTIONABLE. "Needs 268.13 to stay
        afloat" leaves the reader asking when, which is the whole of what they
        would do with the figure: money that arrives after the payment was
        refused did not keep the month afloat. So the clause names the day the
        balance first goes under, which is the day the sum has to beat.

        Deliberately built from the low point rather than from the close: a
        month that dips under mid-month and recovers by payday has still had
        payments refused, so the close cannot be the measure. The DEADLINE is
        the first breach rather than that low, since the first refusal is what
        the money has to get in front of; clearing the low clears every day
        after it too.

        A month with a facility is told what keeps it inside the facility,
        naming the limit, because "afloat" and "not overdrawn" stop meaning
        the same thing the moment borrowing is arranged.
        """
        afloat = MonthAfloat(
            low_point_pence=low_point_pence,
            overdraft_limit_pence=overdraft_limit_pence,
        )
        if afloat.stays_afloat:
            return f"stays afloat, {fmt(afloat.headroom_pence)} clear at its lowest"
        # A month that opens under the floor has already breached, so there is
        # no day to beat: the money is late before the month starts.
        deadline = (
            "now"
            if breach_day is None or breach_day == _LOW_AT_START
            else f"by day {breach_day}"
        )
        if overdraft_limit_pence > 0:
            return (
                f"needs {fmt(afloat.needed_pence)} {deadline} to stay within "
                f"your {fmt(overdraft_limit_pence)} overdraft"
            )
        return f"needs {fmt(afloat.needed_pence)} {deadline} to stay afloat"
