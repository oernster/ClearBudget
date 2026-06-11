"""Overdraft settings and cashflow projection for BudgetService - LOC limit split."""

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.domain.services._prorating import days_in_month
from clear_budget.domain.services.bank_cashflow import (
    BankCashflowService,
    DailyCashflowEvent,
    MonthCashflowProjection,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


class OverdraftOperationsMixin:
    """Overdraft facility settings and month cashflow projection."""

    __slots__ = ()

    def get_overdraft_limit(self) -> Amount:  # pragma: no cover
        from clear_budget.application.services._settings_operations import (
            get_overdraft_limit_pence,
        )

        return Amount(
            pence=get_overdraft_limit_pence(getattr(self.bill_repo, "conn", None))
        )

    def set_overdraft_limit(self, *, amount: Amount) -> None:  # pragma: no cover
        from clear_budget.application.services._settings_operations import (
            set_overdraft_limit_pence,
        )

        set_overdraft_limit_pence(self.bill_repo.conn, amount.pence)

    def get_overdraft_apr_basis_points(self) -> int:  # pragma: no cover
        from clear_budget.application.services._settings_operations import (
            get_overdraft_apr_basis_points,
        )

        return get_overdraft_apr_basis_points(getattr(self.bill_repo, "conn", None))

    def set_overdraft_apr_basis_points(
        self, *, basis_points: int
    ) -> None:  # pragma: no cover
        from clear_budget.application.services._settings_operations import (
            set_overdraft_apr_basis_points,
        )

        set_overdraft_apr_basis_points(self.bill_repo.conn, basis_points)

    def get_month_cashflow_projection(
        self, *, year_month: YearMonth, summary: MonthSummary
    ) -> MonthCashflowProjection:  # pragma: no cover
        """Project the day-by-day bank balance for year_month."""
        opening_pence = self.get_projected_starting_balance_pence(year_month=year_month)
        bills, income = self.get_remaining_month_items(
            year_month=year_month, summary=summary
        )
        total_days = days_in_month(year_month.year, year_month.month)

        events = [
            DailyCashflowEvent(inc.day_of_month or 1, inc.amount.pence)
            for inc in income
        ]
        events += [
            DailyCashflowEvent(b.day_of_month or total_days, -b.amount.pence)
            for b in bills
            if b.payment_method_id == 1
        ]

        return BankCashflowService.project_month(
            starting_balance_pence=opening_pence,
            events=events,
            overdraft_limit_pence=self.get_overdraft_limit().pence,
        )
