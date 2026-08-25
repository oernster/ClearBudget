"""Recommendations adapter for BudgetService - extracted for the LOC limit.

Bridges the pure recommendation engine to the app's stored months. The
reading is deliberately the bank page's own, AS ENTERED: recommendations are
advice about the difficult months the user can already see there, so they
must be computed from the same evidence, not from the repeat-forward
assumption the Safe to Spend page states.

The horizon starts at the month AFTER the current one, opening from the
current month's projected end-of-month balance, exactly as the overdraft
runway walks. The current month's own days are mostly behind it or committed,
so the months ahead are where a retiming or an ask can still land.
"""

from datetime import date

from clear_budget.application.services._overdraft_projection import (
    _BANK_PAYMENT_METHOD_ID,
    _UNDATED_BILL_DAY,
    _UNDATED_INCOME_DAY,
)
from clear_budget.domain.services._prorating import days_in_month
from clear_budget.domain.services.recommendations import (
    KIND_BILL,
    KIND_INCOME,
    PlannedItem,
    PlannedMonth,
    Recommendations,
    recommend,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


def _planned_month(summary, year: int, month: int) -> PlannedMonth:
    """One month's bank-side plan, income listed before bills.

    The construction order carries the shared-day rule: the engine's stable
    sort keeps income ahead of bills on the same day, the same optimistic
    ordering the bank page's projection uses. An item with no day of its own
    takes the projection's day conventions; it is never offered as movable,
    because retiming something with no date is not a suggestion a user can
    act on.
    """
    days = days_in_month(year, month)
    items = [
        PlannedItem(
            name=inc.name,
            kind=KIND_INCOME,
            day=min(inc.day_of_month or _UNDATED_INCOME_DAY, days),
            amount_pence=inc.amount.pence,
            movable=inc.day_of_month is not None and not inc.day_fixed,
        )
        for inc in summary.income_sources
    ]
    items += [
        PlannedItem(
            name=bill.name,
            kind=KIND_BILL,
            day=min(bill.day_of_month or _UNDATED_BILL_DAY, days),
            amount_pence=-bill.amount.pence,
            movable=bill.day_of_month is not None and not bill.day_fixed,
        )
        for bill in summary.bills
        if bill.payment_method_id == _BANK_PAYMENT_METHOD_ID
    ]
    return PlannedMonth(year=year, month=month, days=days, items=tuple(items))


class RecommendationOperationsMixin:
    """Recommendation computation and its buffer setting for BudgetService."""

    __slots__ = ()

    def get_recommendation_buffer(self) -> tuple[bool, Amount]:
        """(enabled, amount): the emergency buffer the target adds.

        Disabled and zero until the user says otherwise: the page invents no
        comfort figure of its own.
        """
        from clear_budget.application.services._settings_operations import (
            get_recommendation_buffer_enabled,
            get_recommendation_buffer_pence,
        )

        conn = getattr(self.bill_repo, "conn", None)
        stored = get_recommendation_buffer_pence(conn)
        enabled = get_recommendation_buffer_enabled(conn)
        return enabled, Amount(pence=0 if stored is None else stored)

    def set_recommendation_buffer(self, *, enabled: bool, amount: Amount) -> None:
        from clear_budget.application.services._settings_operations import (
            set_recommendation_buffer_enabled,
            set_recommendation_buffer_pence,
        )

        set_recommendation_buffer_enabled(self.bill_repo.conn, enabled)
        set_recommendation_buffer_pence(self.bill_repo.conn, amount.pence)

    def get_recommendations(
        self, *, today: date | None = None
    ) -> tuple[Recommendations, tuple[YearMonth, ...]]:
        """The engine's answer plus the months it covers, in order.

        Judged against the agreed overdraft floor plus the buffer while the
        buffer is enabled, against the floor alone while it is not. The
        horizon is the sustainable window, so this page and Safe to Spend
        agree about how far ahead "ahead" reaches.
        """
        today = today or date.today()  # noqa: DTZ011 (naive local dates)
        current = YearMonth(today.year, today.month)
        horizon: list[YearMonth] = []
        cursor = current
        for _ in range(self.get_sustainable_window_months()):
            cursor = cursor.next_month()
            horizon.append(cursor)
        months = tuple(
            _planned_month(self.get_month_summary(year_month=ym), ym.year, ym.month)
            for ym in horizon
        )
        enabled, buffer = self.get_recommendation_buffer()
        result = recommend(
            months=months,
            opening_balance_pence=self.get_projected_month_end_balance_pence(
                year_month=current,
                summary=self.get_month_summary(year_month=current),
            ),
            overdraft_limit_pence=self.get_overdraft_limit().pence,
            buffer_pence=buffer.pence if enabled else 0,
        )
        return result, tuple(horizon)
