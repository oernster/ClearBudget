"""The second reading of the months ahead: what they look like if this repeats.

Every figure on the bank page counts only money entered and marked reliable,
so nothing there is quietly propped up by money that may not come. That
reading is honest but pessimistic about the future, because a month nobody has
filled in yet looks empty rather than unknown. This module renders the other
half of the picture, on a page of its own and never in place of the bank
page's own months:

* the same traffic-light hues, blended toward the page background, so an
  assumed month reads as provisional at a glance without changing what its
  colour means;
* the gap specification names exactly what has to arrive (and when) for the
  assumed reading to come true. A second projection without that list would
  be a wish rather than a plan.

The assumption is DERIVED, not marked: income entered for this month is taken
to arrive again in any later month that has no entry of that name. The block
therefore appears on its own once the months ahead are thinner than this one,
rather than waiting for the user to remember to untick a reliable box. Because
nothing was ticked, the page states the rule outright: a reader cannot infer
a derivation from the figures it produced.

This module owns the lower half of that page: the gap specification and the
months ahead. The Safe to Spend headline above them is rendered by
`_solvency_panel_safe_to_spend`, on the same repeat-forward assumption, so
the whole page is one reading rather than a figure with commentary attached.

The two halves differ in one way on purpose. The headline is outside
`assumed_block()` and always shows, because with nothing to assume it simply
equals what was entered; everything here hides, because with nothing to
assume there is no assumption to state and no month to qualify.
"""

from clear_budget.application.formatting import money_from_pence
from clear_budget.ui import theme
from clear_budget.ui.theme_tokens import assumed_state_colours_for
from clear_budget.ui.utils.format_helpers import MONTH_NAMES


class SolvencyPanelAssumedMixin:
    """Renders the assumed-income second reading on the projection page."""

    def _assumed_colour(self, state_key: str) -> str:
        """The muted variant of a traffic-light state, for the active theme."""
        from PySide6.QtWidgets import QApplication

        return assumed_state_colours_for(theme.current_theme(QApplication.instance()))[
            state_key
        ]

    def _update_assumed(self, report) -> None:
        """Fill the projection page; say why when it has nothing to show."""
        service = self.view_model.budget_service
        expected = service.get_assumed_expectations()
        # The page is reachable by a button, so it must never be blank: with
        # nothing to assume it says that rather than showing an empty column.
        self.assumed_empty_label.setVisible(not expected)
        for widget in self.assumed_block():
            widget.setVisible(bool(expected))
        if not expected:
            return

        self.assumed_gaps_label.setText(self._gap_specification(expected))
        self._render_assumed_forward(report, service.get_overdraft_limit().pence)

    def _render_assumed_forward(self, report, overdraft_limit_pence: int) -> None:
        """The bank page's two months, walked again on the assumption.

        This is what the page is opened for. A bank page that ends in an
        overdrawn month is exactly when someone asks whether the money they
        expect would rescue it. That is a question about those months rather
        than about today.

        Each month is read through the same builder the bank page uses, on a
        summary the service filled forward, so the two pages differ in their
        evidence and never in their arithmetic.
        """
        service = self.view_model.budget_service
        known_here = service.get_month_summary(year_month=report.year_month)
        assumed_here = service.get_assumed_month_summary(year_month=report.year_month)
        # This month's close on the assumption: the known close plus whatever
        # income the assumption counts here that the known reading does not.
        opening = report.balance_pence + (
            assumed_here.total_income.pence - known_here.total_income.pence
        )
        month = report.year_month
        labels = (
            self.m1_assumed_projection_label,
            self.m2_assumed_projection_label,
        )
        for label in labels:
            month = month.next_month()
            summary = service.get_assumed_month_summary(year_month=month)
            # Two figures, because two questions are being asked. The
            # shortfall says what the month must find and drives both its
            # sentence and its colour; the net says what actually leaves the
            # account, so only that may carry the balance to the next month.
            # Money set aside has not gone anywhere.
            net = self._bank_total(summary) - summary.total_income.pence
            shortfall = self._month_shortfall_pence(month, summary)
            text, _colour, clarion = self._build_month_cashflow_summary(
                opening, summary, shortfall, overdraft_limit_pence
            )
            state = self._month_cashflow_state(
                opening, summary, shortfall, overdraft_limit_pence
            )
            self._set_projection_label(
                label,
                heading=f"{MONTH_NAMES[month.month]} {month.year}",
                body=text,
                colour=self._assumed_colour(state),
                clarion=clarion,
            )
            opening -= net

    @staticmethod
    def _gap_specification(expected: list) -> str:
        """What has to arrive (and when) for the assumed reading to hold."""
        lines = ["Depends on money not yet received:"]
        for month, source in expected:
            when = (
                f"by day {source.day_of_month}"
                if source.day_of_month
                else "at any point"
            )
            lines.append(
                f"  {MONTH_NAMES[month.month]} {month.year}: {source.name}"
                f" {money_from_pence(source.amount.pence)} {when}"
            )
        return "\n".join(lines)
