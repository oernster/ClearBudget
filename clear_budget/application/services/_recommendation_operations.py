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
from clear_budget.domain.services.reserve_accrual import (
    occurrence_at,
    reserve_pence,
)
from clear_budget.domain.services.recommendations import (
    KIND_BILL,
    KIND_INCOME,
    KIND_PAUSE,
    PlannedItem,
    PlannedMonth,
    PlannedReserve,
    Recommendations,
    TrialDay,
    immovable_months,
    paused_months,
    recommend,
    retimed_months,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth


def _reserve_by_day(commitments, year: int, month: int) -> tuple[int, ...]:
    """What the commitments hold back on each day of one month.

    Zero everywhere while nothing is set aside, which the engine reads as no
    reserve at all and answers exactly as it always did.
    """
    return tuple(
        sum(reserve_pence(c, date(year, month, day)) for c in commitments)
        for day in range(1, days_in_month(year, month) + 1)
    )


def _planned_reserve(commitment, horizon) -> PlannedReserve | None:
    """One commitment as the engine sees it, else None when it holds nothing.

    The due month is read from the occurrence live at the START of the window
    rather than from the stored due date, so a repeating commitment is priced
    against the cycle the window is actually saving for.
    """
    opening = horizon[0].first_day()
    occurrence = occurrence_at(commitment, opening)
    if occurrence is None:
        return None
    return PlannedReserve(
        name=commitment.name,
        amount_pence=commitment.amount.pence,
        by_day=tuple(
            _reserve_by_day((commitment,), ym.year, ym.month) for ym in horizon
        ),
        due_year=occurrence.due.year,
        due_month=occurrence.due.month,
    )


def _planned_month(summary, year: int, month: int, reserve_by_day=()) -> PlannedMonth:
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
    return PlannedMonth(
        year=year,
        month=month,
        days=days,
        items=tuple(items),
        reserve_by_day=tuple(reserve_by_day),
    )


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
        self,
        *,
        today: date | None = None,
        trial: tuple[TrialDay, ...] = (),
        pinned: bool = False,
    ) -> tuple[Recommendations, tuple[YearMonth, ...]]:
        """The engine's answer plus the months it covers, in order.

        Judged against the agreed overdraft floor plus the buffer while the
        buffer is enabled, against the floor alone while it is not. The
        horizon is the sustainable window, so this page and Safe to Spend
        agree about how far ahead "ahead" reaches.

        `trial` is the try-it-on set: each entry is SIMULATED before the
        engine runs, nothing stored. A retiming puts its item on its trial day
        in every horizon month; a pause stops one commitment's hold-back from
        its month on. The result then reads as "were you to make these
        changes": remaining moves, asks and outlook all reflect them.

        `pinned` additionally pins every item to its (possibly tried) day,
        so the engine proposes nothing of its own. The try-it-on panels
        compare two pinned runs: the normal run's outlook assumes the
        engine's plan applied, which would hide a tick that merely does
        what the plan proposed anyway.
        """
        today = today or date.today()  # noqa: DTZ011 (naive local dates)
        current = YearMonth(today.year, today.month)
        horizon: list[YearMonth] = []
        cursor = current
        for _ in range(self.get_sustainable_window_months()):
            cursor = cursor.next_month()
            horizon.append(cursor)
        commitments = self.list_commitments()
        reserves = tuple(
            reserve
            for reserve in (
                _planned_reserve(commitment, tuple(horizon))
                for commitment in commitments
            )
            if reserve is not None
        )
        # A trial is either a day or a pause; each rewrites the plan in its own
        # way, so they are separated here rather than inside either rewriter.
        days = tuple(t for t in trial if t.kind != KIND_PAUSE)
        pauses = tuple(t for t in trial if t.kind == KIND_PAUSE)
        months = retimed_months(
            tuple(
                _planned_month(
                    self.get_month_summary(year_month=ym),
                    ym.year,
                    ym.month,
                    _reserve_by_day(commitments, ym.year, ym.month),
                )
                for ym in horizon
            ),
            days,
        )
        months = paused_months(months, reserves, pauses)
        if pinned:
            months = immovable_months(months)
        enabled, buffer = self.get_recommendation_buffer()
        result = recommend(
            months=months,
            opening_balance_pence=self.get_projected_month_end_balance_pence(
                year_month=current,
                summary=self.get_month_summary(year_month=current),
            ),
            overdraft_limit_pence=self.get_overdraft_limit().pence,
            buffer_pence=buffer.pence if enabled else 0,
            reserves=reserves,
        )
        return result, tuple(horizon)
