"""Balance and overdraft presentation for MonthView.

The balance label (stored balance for the month the user is in, projected
month-end for any other) and the overdraft warning strip under the nav row.
Split from month_view so each file holds one concern, the same shape as the
table, edit and delete mixins beside it.
"""

from clear_budget.domain.services.bank_cashflow import BankCashflowService
from clear_budget.ui import label_roles
from clear_budget.ui.utils.format_helpers import fmt

# A projected balance below this is shown as thin rather than healthy: one
# hundred pounds of headroom, in pence.
_THIN_BALANCE_PENCE = 10000


class MonthViewBalanceMixin:
    """Balance label and overdraft warning presentation for MonthView."""

    def _get_balance_role(self, p: int) -> str:
        """Severity role for a balance: negative, thin or healthy."""
        if p < 0:
            return label_roles.DANGER
        return label_roles.WARN if p < _THIN_BALANCE_PENCE else label_roles.GOOD

    def _update_balance_display(self) -> None:
        if summary := self.view_model.month_summary:
            from datetime import datetime as _dt

            from clear_budget.domain.value_objects.year_month import YearMonth as _YM

            now = _dt.now()  # noqa: DTZ005 (app runs on naive local time)
            today_ym = _YM(now.year, now.month)
            if self.view_model.current_month == today_ym:
                # Elapsed dated bills/income are folded into the stored
                # balance at midnight (and at startup), so it is shown as-is.
                pence = self.view_model.budget_service.get_bank_balance().pence
                label = f"Balance: {fmt(pence)}"
            else:
                _svc = self.view_model.budget_service
                pence = _svc.get_projected_month_end_balance_pence(
                    year_month=self.view_model.current_month,
                    summary=summary,
                )
                if pence >= 0:
                    label = f"Projected end: {fmt(pence)}"
                else:
                    label = f"Projected end: -{fmt(abs(pence))} OVERDRAWN"
            self.balance_label.setText(label)
            label_roles.set_role(self.balance_label, self._get_balance_role(pence))
            self._update_overdraft_warning(summary)

    def _update_overdraft_warning(self, summary) -> None:
        svc = self.view_model.budget_service
        projection = svc.get_month_cashflow_projection(
            year_month=self.view_model.current_month, summary=summary
        )
        overdraft_limit_pence = svc.get_overdraft_limit().pence
        severity = projection.overdraft_severity(overdraft_limit_pence)
        if severity == "none":
            self.overdraft_warning_label.setVisible(False)
            return

        low = fmt(abs(projection.min_balance_pence))
        day = projection.min_balance_day
        if severity == "amber":
            text = (
                f"⚠ Balance dips to -{low} around day {day} (covered by your overdraft)"
            )
            daily_interest = (
                BankCashflowService.estimate_daily_overdraft_interest_pence(
                    abs(projection.min_balance_pence),
                    svc.get_overdraft_apr_basis_points(),
                )
            )
            if daily_interest > 0:
                text += f" - ~{fmt(daily_interest)}/day interest"
            role = label_roles.WARN_NOTE
        elif overdraft_limit_pence > 0:
            text = (
                f"⚠ Balance may EXCEED your overdraft limit (-{low} around day {day})"
            )
            role = label_roles.DANGER_NOTE
        else:
            text = (
                f"⚠ Balance may go OVERDRAWN to -{low} around day {day}"
                " - no overdraft facility set"
            )
            role = label_roles.DANGER_NOTE

        self.overdraft_warning_label.setText(text)
        label_roles.set_role(self.overdraft_warning_label, role)
        self.overdraft_warning_label.setVisible(True)
