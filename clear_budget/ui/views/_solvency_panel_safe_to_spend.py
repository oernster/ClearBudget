"""Safe to Spend Today rendering for SolvencyPanel - extracted for LOC limit.

Owns one concern: turning a SustainableResult into the headline banner and
its secondary line. The number's semantics live in the domain calculation;
this module only decides what a person reads.
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

    def _update_safe_to_spend(self) -> None:
        """Render the headline: what can be spent with the window still standing.

        The number is never the minimum of a healthy stretch with the bad
        months excluded. Every day of the window has a veto, because money
        spent today lowers the bad days too: a figure that ignored them would
        fund its own deficit and read as safe while the month after collapsed
        by exactly that much more.

        So a window that cannot survive reports NOTHING spendable and names
        what it is short by. That number is money to be found, not spent.
        """
        service = self.view_model.budget_service
        result = service.get_safe_to_spend()
        months = service.get_sustainable_window_months()
        window = f"{months} months" if months != 1 else "month"
        if result.amount_pence < 0:
            self.sts_banner.setText(
                f"NOTHING SAFE TO SPEND: the next {window} are"
                f" {money_from_pence(abs(result.amount_pence))} short"
            )
            state = STATE_RED
            detail = (
                f"The shortfall lands on {self._sts_day(result.binding_day)}."
                f" That is money to find rather than money to spend"
            )
        elif result.amount_pence == 0:
            self.sts_banner.setText("Nothing safe to spend today")
            state = STATE_AT_RISK
            detail = self._sts_detail_line(result, window)
        else:
            self.sts_banner.setText(
                f"{money_from_pence(result.amount_pence)} safe to spend today"
            )
            state = STATE_SAFE
            detail = self._sts_detail_line(result, window)
        self._update_capacity()
        self.sts_detail.setText(detail)
        self.sts_detail.setVisible(bool(detail))
        self.sts_banner.setProperty("state", state)
        _repolish_role(self.sts_banner, self.sts_banner.objectName())

    def _update_capacity(self) -> None:
        """Show how the spendable figure moves as money lands this month.

        The headline is about today; today is often the worst day of the
        month: waiting for an income to land raises what the account can
        carry. Each row is the figure from that day onward, so a row answers
        "what could I spend if I wait until then". The first step repeats
        the headline, so it is dropped: only the changes are news.

        Every row is still measured across the whole window, so waiting can
        never raise the figure past what the later months will bear.
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

    def _sts_detail_line(self, result, window: str) -> str:
        """Secondary line under a spendable headline.

        Names the promise the figure keeps (every day of the window above the
        buffer) and the day that limits it, so the number can be checked
        against the projection rather than taken on trust.
        """
        detail = f"Keeps the next {window} above"
        if result.floor_pence > 0:
            detail += f" your {money_from_pence(result.floor_pence)} buffer"
        else:
            detail += " zero"
        return detail + f"; constrained by {self._sts_day(result.binding_day)}"
