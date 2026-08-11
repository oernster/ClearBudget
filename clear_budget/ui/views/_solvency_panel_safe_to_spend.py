"""Safe to Spend Today rendering for SolvencyPanel - extracted for LOC limit.

Owns one concern: turning a SafeToSpendResult into the headline banner and
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

        The full-forecast horizon can bind years out, where "10 Jun" alone
        would read as this year's June.
        """
        label = f"{day.day} {MONTH_NAMES[day.month][:3]}"
        today = _date.today()  # noqa: DTZ011 (local date)
        if day.year != today.year:
            label += f" {day.year}"
        return label

    def _update_safe_to_spend(self) -> None:
        """Render the Safe to Spend Today headline from the live projection.

        Always about today, whichever month is being viewed: the number is
        what could leave the account now without pushing any day of the
        still-healthy stretch below the safety floor. Days the baseline
        forecast already has under the floor are a warning of their own (the
        secondary line names when they start); they are never summed into
        the number, because a dip accumulated across future months would
        read as a debt owed today, which it is not.
        """
        result = self.view_model.budget_service.get_safe_to_spend()
        if result.amount_pence < 0:
            # Today itself is already under the floor; the answer to "what
            # can I spend today" is nothing, so say that.
            if result.floor_pence > 0:
                self.sts_banner.setText(
                    f"NOTHING SAFE TO SPEND: already below your"
                    f" {money_from_pence(result.floor_pence)} floor"
                )
            else:
                self.sts_banner.setText("NOTHING SAFE TO SPEND: already under")
            state = STATE_RED
            detail = ""
        elif result.amount_pence == 0:
            self.sts_banner.setText("Nothing safe to spend today")
            state = STATE_AT_RISK
            detail = self._sts_detail_line(result)
        else:
            self.sts_banner.setText(
                f"{money_from_pence(result.amount_pence)} safe to spend today"
            )
            # A later breach does not change the amount (those days are
            # under regardless of today's spending) but it tempers the tone.
            state = STATE_AT_RISK if result.first_breach_day else STATE_SAFE
            detail = self._sts_detail_line(result)
        self.sts_detail.setText(detail)
        self.sts_detail.setVisible(bool(detail))
        self.sts_banner.setProperty("state", state)
        _repolish_role(self.sts_banner, self.sts_banner.objectName())

    def _sts_detail_line(self, result) -> str:
        """Secondary line under a non-negative headline.

        Names the constraining day and the reserve when one is set; when the
        baseline forecast goes under later regardless of spending, it also
        names the day that trouble starts.
        """
        detail = f"Constrained by {self._sts_day(result.binding_day)}"
        if result.floor_pence > 0:
            detail += f", keeping {money_from_pence(result.floor_pence)} in reserve"
        if result.first_breach_day is not None:
            under = "drops below your floor" if result.floor_pence > 0 else "goes under"
            detail += (
                f"; the forecast {under} from"
                f" {self._sts_day(result.first_breach_day)} regardless"
            )
        return detail
