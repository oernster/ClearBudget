"""Safe-to-spend settings and projection adapter for BudgetService.

Bridges the pure safe_to_spend calculation to the app's existing forecast:
the current month comes from the same anchored day-by-day series the month
graph draws, and later months chain from its close using the same per-day
event rules, so the headline number can never disagree with the graph.
"""

from datetime import date

from clear_budget.application.services._overdraft_projection import (
    _DEFAULT_HORIZON_MONTHS,
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


def _income_dates(summary, year_month: YearMonth, *, current: bool) -> list[date]:
    """Dates the month's income events land on, as the projection counts them.

    For the current month an income already marked Received is part of the
    stored balance rather than a future event, so it cannot end the horizon.
    """
    days = days_in_month(year_month.year, year_month.month)
    return [
        date(
            year_month.year,
            year_month.month,
            min(inc.day_of_month or _UNDATED_INCOME_DAY, days),
        )
        for inc in summary.income_sources
        if not (current and inc.received_for_month)
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
        """Stored horizon strategy, defaulting to UNTIL_NEXT_INCOME."""
        from clear_budget.application.services._settings_operations import (
            get_safe_to_spend_horizon,
        )

        stored = get_safe_to_spend_horizon(getattr(self.bill_repo, "conn", None))
        try:
            return HorizonStrategy(stored)
        except ValueError:
            return HorizonStrategy.UNTIL_NEXT_INCOME

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

        The current month reuses the anchored graph series; later months
        chain day by day from its close, exactly as the runway search does.
        """
        ym = YearMonth(today.year, today.month)
        summary = self.get_month_summary(year_month=ym)
        series = self.get_bank_graph_series(year_month=ym, summary=summary, today=today)
        projection = [
            DayProjection(day=date(ym.year, ym.month, i + 1), balance_pence=pence)
            for i, pence in enumerate(series.values)
        ]
        income_days = _income_dates(summary, ym, current=True)

        balance = series.values[-1]
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
            income_days += _income_dates(summary, cursor, current=False)
        return projection, income_days
