"""The second reading: what the months look like IF this month repeats.

Every figure elsewhere in the app counts only money entered and marked
reliable, so nothing is quietly propped up by money that may not come. That
reading is honest but pessimistic about the future, because a month nobody has
filled in yet looks empty rather than unknown. This module adds the other half
of the picture on a page of its own, never instead of those figures:

* the same traffic-light hues, blended toward the page background, so an
  assumed figure reads as provisional at a glance without changing what its
  colour means;
* every line says plainly that it depends on money not yet received;
* the gap specification names exactly what has to arrive (and when) for the
  assumed reading to come true. A second projection without that list would
  be a wish rather than a plan.

The assumption is DERIVED, not marked: income entered for this month is taken
to arrive again in any later month that has no entry of that name. The block
therefore appears on its own once the months ahead are thinner than this one,
rather than waiting for the user to remember to untick a reliable box. Because
nothing was ticked, the page states the rule outright: a reader cannot infer
a derivation from the figures it produced.

The page answers the bank page's questions in the bank page's order and it
carries both terms of every comparison it draws. Its earlier shape was a
muted figure with no noun beside a phrase comparing it to a number on the
other page, which asked the reader to remember the bank page rather than to
read this one.
"""

from clear_budget.application.formatting import money_from_pence
from clear_budget.application.projection_basis import ProjectionBasis
from clear_budget.ui import theme, ui_scale
from clear_budget.ui._theme_labels import BANNER_FONT_PX
from clear_budget.ui.theme_tokens import assumed_state_colours_for
from clear_budget.ui.utils.format_helpers import MONTH_NAMES

# Unscaled type size of an assumed line, a step below the figure it qualifies.
_ASSUMED_FONT_PX = 15
# The provisional banner: the bank banner's size and padding so the figure is
# as findable, an outline instead of a fill so it never reads as settled.
_ASSUMED_BANNER_BORDER_PX = 2
_ASSUMED_BANNER_PADDING_PX = 10
_ASSUMED_BANNER_RADIUS_PX = 5


class SolvencyPanelAssumedMixin:
    """Renders the assumed-income second reading on the projection page."""

    def _assumed_colour(self, state_key: str) -> str:
        """The muted variant of a traffic-light state, for the active theme."""
        from PySide6.QtWidgets import QApplication

        return assumed_state_colours_for(theme.current_theme(QApplication.instance()))[
            state_key
        ]

    def _style_assumed(self, label, state_key: str) -> None:
        """Paint an assumed line in the muted variant of its own state."""
        label.setStyleSheet(
            ui_scale.style(
                f"font-size: {_ASSUMED_FONT_PX}px; padding: 2px 5px;"
                f" font-style: italic; color: {self._assumed_colour(state_key)};"
            )
        )

    def _style_assumed_banner(self, state_key: str) -> None:
        """Paint the provisional headline: banner weight, no fill.

        A filled banner would give an assumed figure the standing the bank
        page's known one has, which is the confusion this page exists to
        avoid. An outline in the same muted hue keeps the prominence and
        withholds the authority.
        """
        colour = self._assumed_colour(state_key)
        self.sts_assumed_banner.setStyleSheet(
            ui_scale.style(
                f"font-size: {BANNER_FONT_PX}px; font-weight: bold;"
                f" padding: {ui_scale.px(_ASSUMED_BANNER_PADDING_PX)}px;"
                f" border: {ui_scale.px(_ASSUMED_BANNER_BORDER_PX)}px solid {colour};"
                f" border-radius: {ui_scale.px(_ASSUMED_BANNER_RADIUS_PX)}px;"
                f" color: {colour};"
            )
        )

    @staticmethod
    def _spendable_sentence(amount_pence: int) -> str:
        """One spendable figure said in full, on either basis.

        Both readings are said the same way, because the point of showing
        them together is that they answer the same question from different
        evidence. Wording them differently would make the comparison look
        like a comparison of two different quantities.
        """
        if amount_pence < 0:
            return (
                "Nothing safe to spend today:"
                f" {money_from_pence(abs(amount_pence))} short"
            )
        if amount_pence == 0:
            return "Nothing safe to spend today"
        return f"{money_from_pence(amount_pence)} safe to spend today"

    def _update_assumed(self, report) -> None:
        """Fill the projection page; say why when it has nothing to show.

        Runs the same calculations as the known reading on the repeat basis,
        so the two are one engine read twice rather than two engines that
        could disagree.
        """
        service = self.view_model.budget_service
        expected = service.get_assumed_expectations()
        # The page is reachable by a button, so it must never be blank: with
        # nothing to assume it says that rather than showing an empty column.
        self.assumed_empty_label.setVisible(not expected)
        for widget in self.assumed_block():
            widget.setVisible(bool(expected))
        if not expected:
            return

        known = service.get_spending_capacity()
        probable = service.get_spending_capacity(basis=ProjectionBasis.REPEAT_CURRENT)
        overdraft_limit_pence = service.get_overdraft_limit().pence
        state = self._state_key(
            probable[-1].amount_pence, 0, False, overdraft_limit_pence
        )
        self.sts_assumed_banner.setText(
            self._spendable_sentence(probable[0].amount_pence)
        )
        self._style_assumed_banner(state)
        # The known figure is a fact, so it keeps the plain muted role rather
        # than an assumed hue: only the assumed figures are spoken quietly.
        # It appears only when the two readings differ, on the same grounds
        # the bank page hides its capacity rows on a flat month: restating an
        # identical figure is the schedule's "no change" line said twice.
        self.sts_assumed_known.setText(
            "Counting only money already entered: "
            + self._spendable_sentence(known[0].amount_pence)
        )
        self.sts_assumed_known.setVisible(
            probable[0].amount_pence != known[0].amount_pence
        )
        self.sts_assumed.setText(self._assumed_capacity_text(known, probable))
        self._style_assumed(self.sts_assumed, state)
        self.assumed_gaps_label.setText(self._gap_specification(expected))
        self._style_assumed(self.assumed_gaps_label, state)
        self._render_assumed_forward(report, overdraft_limit_pence)

    def _render_assumed_forward(self, report, overdraft_limit_pence: int) -> None:
        """The bank page's two months, walked again on the assumption.

        This is what the page is opened for. A bank page that ends in an
        overdrawn month is exactly when someone asks whether the money they
        expect would rescue it; a spendable figure alone cannot answer that,
        because it says what today allows, never what October does.

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
            drain = self._bank_total(summary) - summary.total_income.pence
            text, _colour, clarion = self._build_month_cashflow_summary(
                opening, summary, drain, overdraft_limit_pence
            )
            state = self._month_cashflow_state(
                opening, summary, drain, overdraft_limit_pence
            )
            self._set_projection_label(
                label,
                heading=f"{MONTH_NAMES[month.month]} {month.year}",
                body=text,
                colour=self._assumed_colour(state),
                clarion=clarion,
            )
            opening -= drain

    def _assumed_capacity_text(self, known, probable) -> str:
        """The spendable schedule again, with the expected income counted.

        Mirrors the known schedule rather than restating today's headline,
        because today is usually constrained by a day too near to care what a
        later month receives: the difference the expected money makes shows up
        in what waiting buys, not in what today allows.
        """
        if [(s.from_day, s.amount_pence) for s in probable] == [
            (s.from_day, s.amount_pence) for s in known
        ]:
            return "No change: the expected income falls outside what limits you now"
        lines = []
        for step in probable:
            lines.append(
                f"From {self._sts_day(step.from_day)}:"
                f" {money_from_pence(step.amount_pence)}"
                f" (held down by {self._sts_day(step.binding_day)})"
            )
        # Naming the direction matters: making a later month survive extends
        # the horizon, so the assumed figure is frequently LOWER than the known
        # one. Read without that said, it looks like a mistake.
        if probable[-1].amount_pence < known[-1].amount_pence:
            lines.append(
                "Lower than the known figure, because surviving longer means"
                " the later months now count against today"
            )
        return "\n".join(lines)

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
