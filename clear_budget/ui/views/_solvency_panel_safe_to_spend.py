"""Safe to Spend rendering for SolvencyPanel - extracted for LOC limit.

Owns one concern: turning a SustainableResult into the headline banner and
the two lines under it. The number's semantics live in the domain
calculation; this module only decides what a person reads.

It renders onto the PROJECTION page and reads the REPEAT_CURRENT basis, so
the figure counts the income this month has in every later month that has no
entry of that name. That placement is the point of it. A spendable figure
sitting on the bank page was read as a plain fact about money in the account,
which it is not. It is a promise about months that have not happened, months
usually thinner on screen than in life simply because their ad hoc income
has not been typed in yet. On the projection page the
assumption it rests on is stated directly beneath it, so the figure is read
with its terms rather than apart from them.
"""

from datetime import date as _date

from clear_budget.application.formatting import money_from_pence
from clear_budget.ui.label_roles import set_role as _repolish_role
from clear_budget.ui.theme_tokens import STATE_AT_RISK, STATE_RED, STATE_SAFE
from clear_budget.ui.utils.format_helpers import MONTH_NAMES


class SolvencyPanelSafeToSpendMixin:
    """Renders the Safe to Spend Today headline."""

    @staticmethod
    def _sts_day(day) -> str:
        """A short day label ("28 Aug"), with the year when it is not this one.

        A window several months long can bind into next year, where "10 Jun"
        alone would read as this year's June.
        """
        label = f"{day.day} {MONTH_NAMES[day.month][:3]}"
        today = _date.today()  # noqa: DTZ011 (local date)
        if day.year != today.year:
            label += f" {day.year}"
        return label

    @staticmethod
    def _sts_month(day) -> str:
        """A month label ("October 2026"), for naming how far a promise reaches."""
        return f"{MONTH_NAMES[day.month]} {day.year}"

    def _update_safe_to_spend(self) -> None:
        """Render the headline: what can be spent, plus how far that holds.

        Measured on the repeat basis (see the module docstring), so the
        figure and the assumption stated under it on the same page describe
        one reading rather than two.

        The figure answers "what can I spend today", so it is bounded by the
        last month that still stands on its own. A month already under the
        floor with nothing spent is not a spending limit but a shortfall.
        Letting it drive the headline answered "does my budget hold" in
        the slot reserved for the other question: the banner read NOTHING
        SAFE TO SPEND while the months in front of it had real headroom.

        The shortfall is not discarded either, which is what made the older
        truncating version dishonest. It gets a line of its own naming the
        month, the amount and the fact that spending the headline deepens
        it, rendered red because it is the one statement here that no
        amount of restraint answers.
        """
        service = self.view_model.budget_service
        result = service.get_safe_to_spend()
        if result.amount_pence < 0:
            self.sts_banner.setText(
                "NOTHING SAFE TO SPEND: this month is"
                f" {money_from_pence(abs(result.amount_pence))} short"
            )
            state = STATE_RED
            # The whole sentence is the shortfall statement here, so it goes
            # to the red label and the reach line has nothing left to say.
            detail = ""
            shortfall = (
                f"The shortfall lands on {self._sts_day(result.binding_day)}."
                f" That is money to find rather than money to spend"
            )
        elif result.amount_pence == 0:
            self.sts_banner.setText("Nothing safe to spend today")
            state = STATE_AT_RISK
            detail, shortfall = self._sts_detail_lines(result)
        else:
            self.sts_banner.setText(
                f"{money_from_pence(result.amount_pence)} safe to spend today"
            )
            state = STATE_AT_RISK if result.has_shortfall else STATE_SAFE
            detail, shortfall = self._sts_detail_lines(result)
        self._update_capacity()
        self.sts_detail.setText(detail)
        self.sts_detail.setVisible(bool(detail))
        self.sts_shortfall.setText(shortfall)
        self.sts_shortfall.setVisible(bool(shortfall))
        self.sts_banner.setProperty("state", state)
        _repolish_role(self.sts_banner, self.sts_banner.objectName())

    def _update_capacity(self) -> None:
        """Show how the spendable figure moves as money lands this month.

        The headline is about today; today is often the worst day of the
        month: waiting for an income to land raises what the account can
        carry. Each row is the figure from that day onward, so a row answers
        "what could I spend if I wait until then". The first step repeats
        the headline, so it is dropped: only the changes are news.

        Every row is measured over the same stretch the headline promises,
        so waiting can never raise the figure past what the months it names
        will bear.
        """
        steps = self.view_model.budget_service.get_spending_capacity()
        rows = [
            f"From {self._sts_day(step.from_day)}:"
            f" {money_from_pence(step.amount_pence)}"
            f" (held down by {self._sts_day(step.binding_day)})"
            for step in steps[1:]
        ]
        if not rows:
            self.sts_capacity.setText("")
            self.sts_capacity.setVisible(False)
            return
        self.sts_capacity.setText("If you wait:\n" + "\n".join(rows))
        self.sts_capacity.setVisible(True)

    def _sts_detail_lines(self, result) -> tuple[str, str]:
        """The two statements under a spendable headline, told apart.

        The first names how far the promise reaches and the day that limits
        it, so the figure can be checked against the projection rather than
        taken on trust. The second appears only when a later month cannot be
        saved by spending nothing: without it the headline would read as an
        all-clear, which is the failure the truncating version had.

        They are returned separately, then rendered into separate labels,
        because they are not the same KIND of statement. The first is a
        caution about a figure the reader can still act on; the second reports
        a gap no restraint closes. Sharing one muted line made the second read
        as more small print under the first, which is how a reader skips the
        one sentence on the page that spending cannot answer.
        """
        detail = f"Holds every day through {self._sts_month(result.covered_end)} above"
        if result.floor_pence > 0:
            detail += f" your {money_from_pence(result.floor_pence)} buffer"
        else:
            detail += " zero"
        detail += f"; constrained by {self._sts_day(result.binding_day)}"
        if not result.has_shortfall:
            return detail, ""
        return detail, (
            f"{self._sts_month(result.shortfall_day)} is"
            f" {money_from_pence(result.shortfall_pence)} short whatever you do;"
            " spending this deepens it"
        )
