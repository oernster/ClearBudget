"""Safe-to-spend settings and projection adapter for BudgetService.

Bridges the pure safe_to_spend calculation to the app's existing forecast.
The current month runs on the SAME still-due convention the rest of the
Solvency panel shows: today's stored balance plus the remaining items, with
an undated bill counted at its prorated remaining portion, because the
elapsed portion of an undated bill is already inside the stored balance.
(The raw month-graph convention charges the full undated amount again near
month end, which double-counts the elapsed spending and made the headline
call days unsafe that the panel's own timeline showed as safe.) Later months
chain from that close using the same per-day event rules as the runway
search, so the headline agrees with the panel's Forward Projection.
"""

from datetime import date

from clear_budget.application.services._overdraft_projection import (
    _BANK_PAYMENT_METHOD_ID,
    _DEFAULT_HORIZON_MONTHS,
    _UNDATED_BILL_DAY,
    _UNDATED_INCOME_DAY,
)
from clear_budget.domain.services._prorating import days_in_month
from clear_budget.domain.services.safe_to_spend import (
    DayProjection,
    HorizonStrategy,
    SafeToSpendResult,
    safe_to_spend,
)
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth

# The forecast window is the same one the overdraft-runway search walks, so
# FULL_FORECAST and the runway always agree on how far ahead the app looks.
_FORECAST_WINDOW_MONTHS = _DEFAULT_HORIZON_MONTHS


def _income_dates(summary, year_month: YearMonth) -> list[date]:
    """Dates a FUTURE month's income events land on, as the projection counts them."""
    days = days_in_month(year_month.year, year_month.month)
    return [
        date(
            year_month.year,
            year_month.month,
            min(inc.day_of_month or _UNDATED_INCOME_DAY, days),
        )
        for inc in summary.income_sources
    ]


class SafeToSpendOperationsMixin:
    """Safe-to-spend calculation and its settings for BudgetService."""

    __slots__ = ()

    def get_safe_to_spend_floor(self) -> Amount:  # pragma: no cover
        from clear_budget.application.services._settings_operations import (
            get_safe_to_spend_floor_pence,
        )

        return Amount(
            pence=get_safe_to_spend_floor_pence(getattr(self.bill_repo, "conn", None))
        )

    def set_safe_to_spend_floor(self, *, amount: Amount) -> None:  # pragma: no cover
        from clear_budget.application.services._settings_operations import (
            set_safe_to_spend_floor_pence,
        )

        set_safe_to_spend_floor_pence(self.bill_repo.conn, amount.pence)

    def get_safe_to_spend_horizon(self) -> HorizonStrategy:
        """Stored horizon strategy, defaulting to FULL_FORECAST.

        The default is the whole forecast because a spend today lowers every
        later day: a horizon stopping at the next payday overstates safety
        whenever a later month does not pay for itself.
        """
        from clear_budget.application.services._settings_operations import (
            get_safe_to_spend_horizon,
        )

        stored = get_safe_to_spend_horizon(getattr(self.bill_repo, "conn", None))
        try:
            return HorizonStrategy(stored)
        except ValueError:
            return HorizonStrategy.FULL_FORECAST

    def set_safe_to_spend_horizon(
        self, *, horizon: HorizonStrategy
    ) -> None:  # pragma: no cover
        from clear_budget.application.services._settings_operations import (
            set_safe_to_spend_horizon,
        )

        set_safe_to_spend_horizon(self.bill_repo.conn, horizon.value)

    def get_safe_to_spend(self, *, today: date | None = None) -> SafeToSpendResult:
        """Safe to Spend Today, from the stored floor and horizon settings.

        `today` is injectable so the result is decided by its inputs rather
        than by the day the code happens to run.
        """
        today = today or date.today()  # noqa: DTZ011 (naive local dates)
        projection, income_days = self._build_safe_to_spend_inputs(today)
        return safe_to_spend(
            projection=projection,
            today=today,
            income_days=income_days,
            floor_pence=self.get_safe_to_spend_floor().pence,
            horizon=self.get_safe_to_spend_horizon(),
        )

    def _build_safe_to_spend_inputs(
        self, today: date
    ) -> tuple[list[DayProjection], list[date]]:
        """Per-day projection and income dates across the forecast window.

        The current month runs from today's stored balance over the same
        remaining items the Solvency panel's own timeline uses (dated items
        still to come, undated bills at their prorated remaining portion, an
        income already marked Received excluded because it is inside the
        stored balance). Its close therefore equals the panel's projected
        end-of-month figure. Later months chain day by day from that close,
        exactly as the runway search does.
        """
        ym = YearMonth(today.year, today.month)
        summary = self.get_month_summary(year_month=ym)
        days = days_in_month(ym.year, ym.month)
        bills, income = self._apply_current_month_filters(
            summary.bills, summary.income_sources, ym, ym, today.day
        )
        per_day = [0] * (days + 1)
        income_days: list[date] = []
        for inc in income:
            if inc.received_for_month:
                continue
            nominal = min(inc.day_of_month or _UNDATED_INCOME_DAY, days)
            income_days.append(date(ym.year, ym.month, nominal))
            # An event whose nominal day has already passed (an undated
            # income, an overdue one) lands on the earliest day it still can.
            per_day[max(nominal, today.day)] += inc.amount.pence
        for bill in bills:
            if bill.payment_method_id != _BANK_PAYMENT_METHOD_ID:
                continue
            nominal = min(bill.day_of_month or _UNDATED_BILL_DAY, days)
            per_day[max(nominal, today.day)] -= bill.amount.pence

        balance = self.get_bank_balance().pence
        projection = []
        for day in range(today.day, days + 1):
            balance += per_day[day]
            projection.append(
                DayProjection(day=date(ym.year, ym.month, day), balance_pence=balance)
            )

        cursor = ym
        for _ in range(_FORECAST_WINDOW_MONTHS - 1):
            cursor = cursor.next_month()
            summary = self.get_month_summary(year_month=cursor)
            days = days_in_month(cursor.year, cursor.month)
            per_day = self._per_day_pence(summary, days)
            for day in range(1, days + 1):
                balance += per_day[day]
                projection.append(
                    DayProjection(
                        day=date(cursor.year, cursor.month, day),
                        balance_pence=balance,
                    )
                )
            income_days += _income_dates(summary, cursor)
        return projection, income_days
