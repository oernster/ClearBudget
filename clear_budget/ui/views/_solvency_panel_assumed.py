"""The second reading: what the months look like IF this month repeats.

Every figure elsewhere in the app counts only money entered and marked
reliable, so nothing is quietly propped up by money that may not come. That
reading is honest but pessimistic about the future, because a month nobody has
filled in yet looks empty rather than unknown. This module adds the other half
of the picture beside those figures, never instead of them:

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
rather than waiting for the user to remember to untick a reliable box.
"""

from clear_budget.application.formatting import money_from_pence
from clear_budget.application.projection_basis import ProjectionBasis
from clear_budget.ui import theme, ui_scale
from clear_budget.ui.theme_tokens import assumed_state_colours_for
from clear_budget.ui.utils.format_helpers import MONTH_NAMES

# Unscaled type size of an assumed line, a step below the figure it qualifies.
_ASSUMED_FONT_PX = 15


class SolvencyPanelAssumedMixin:
    """Renders the assumed-income second reading on the bank page."""

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

    def _update_assumed(self, report) -> None:
        """Fill the assumed block, hiding it when nothing is expected.

        Runs the same calculations as the known reading on the repeat basis,
        so the two are one engine read twice rather than two engines that
        could disagree.
        """
        service = self.view_model.budget_service
        expected = service.get_assumed_expectations()
        if not expected:
            for label in (
                self.assumed_heading,
                self.sts_assumed,
                self.assumed_gaps_label,
            ):
                label.setVisible(False)
            return

        for label in (self.assumed_heading, self.sts_assumed, self.assumed_gaps_label):
            label.setVisible(True)

        known = service.get_spending_capacity()
        probable = service.get_spending_capacity(basis=ProjectionBasis.REPEAT_CURRENT)
        self.sts_assumed.setText(self._assumed_capacity_text(known, probable))
        state = self._state_key(
            probable[-1].amount_pence, 0, False, service.get_overdraft_limit().pence
        )
        self._style_assumed(self.sts_assumed, state)
        self.assumed_gaps_label.setText(self._gap_specification(expected))
        self._style_assumed(self.assumed_gaps_label, state)

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
