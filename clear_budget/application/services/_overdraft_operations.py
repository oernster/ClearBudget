"""Overdraft settings and cashflow projection for BudgetService - LOC limit split."""

from clear_budget.application.dto.month_summary import MonthSummary
from clear_budget.domain.services._prorating import days_in_month
from clear_budget.domain.services.bank_cashflow import (
    BankCashflowService,
    DailyCashflowEvent,
    MonthCashflowProjection,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.month_gap import MonthGap
from clear_budget.domain.value_objects.year_month import YearMonth

# Bills paid from the bank account rather than from a card; only these can
# widen or close the bank gap.
_BANK_PAYMENT_METHOD_ID = 1


class OverdraftOperationsMixin:
    """Overdraft facility settings and month cashflow projection."""

    __slots__ = ()

    def get_month_gap(self, *, year_month: YearMonth) -> MonthGap:
        """What this month costs against what it brings in.

        Whole-month figures on both sides, so the answer describes the SHAPE
        of the month rather than how far through it we are. That is the point
        of it: the still-due total and the projected close already answer
        "where am I now"; neither says what a month like this needs.

        Card interest is gathered here too but kept separate on the value
        object, because it accrues on the cards and never leaves the bank
        account.
        """
        summary = self.get_month_summary(year_month=year_month)
        bank_bills = sum(
            b.amount.pence
            for b in summary.bills
            if b.payment_method_id == _BANK_PAYMENT_METHOD_ID
        )
        card_interest = sum(
            state.monthly_interest.pence
            for state in self.get_card_monthly_states(year_month=year_month)
        )
        return MonthGap(
            income_pence=summary.total_income.pence,
            bank_bills_pence=bank_bills,
            card_interest_pence=card_interest,
        )

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

    def first_overdrawn_month(
        self,
        *,
        from_year_month: YearMonth,
        from_balance_pence: int,
        overdraft_limit_pence: int = 0,
    ) -> YearMonth | None:
        """First future month whose projected balance breaches the floor, else None.

        ``from_balance_pence`` is the projected end-of-month balance of
        ``from_year_month`` (a SolvencyReport.balance_pence). A month counts once
        its balance drops below the agreed overdraft floor
        (``-overdraft_limit_pence``, i.e. below zero when no facility is
        defined). The UI uses the result to state the overdraft runway.
        """
        from clear_budget.application.services._overdraft_projection import (
            first_overdrawn_month as _impl,
        )

        return _impl(
            get_month_summary=self.get_month_summary,
            from_year_month=from_year_month,
            from_balance_pence=from_balance_pence,
            overdraft_limit_pence=overdraft_limit_pence,
        )

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
