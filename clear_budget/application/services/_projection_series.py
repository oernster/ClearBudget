"""Multi-month projection for BudgetService - the path of solvency over time.

The month graph answers "how does this month go". This answers "where is
this heading", by running the same day-by-day projection over a range of
months and reducing each to the handful of figures that describe it: where it
opens, where it closes, and how low it gets on the way.

The low matters more than the close. A month that opens and closes in credit
can still bounce a payment in the third week, and a report that only carried
opening and closing balances would hide exactly the problem it exists to
surface.
"""

from calendar import month_name

from clear_budget.application.dto.projection_month import ProjectionMonth
from clear_budget.domain.value_objects.year_month import YearMonth

_MONTHS_IN_YEAR = 12


def months_between(start: YearMonth, end: YearMonth) -> list[YearMonth]:
    """Every month from `start` to `end` inclusive, ascending.

    A range given backwards yields nothing rather than looping for ever.
    """
    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(YearMonth(year, month))
        month += 1
        if month > _MONTHS_IN_YEAR:
            year, month = year + 1, 1
    return months


class ProjectionSeriesMixin:
    """Multi-month projection provider for BudgetService."""

    __slots__ = ()

    def get_projection_months(
        self, *, start: YearMonth, end: YearMonth
    ) -> list[ProjectionMonth]:
        """Project every month from `start` to `end` inclusive.

        Each month reuses the same day-by-day bank projection the month graph
        draws, so the report and the graph can never disagree about a month
        they both cover.
        """
        floor_pence = -abs(self.get_overdraft_limit().pence)
        projected = []
        for year_month in months_between(start, end):
            summary = self.get_month_summary(year_month=year_month)
            series = self.get_bank_graph_series(year_month=year_month, summary=summary)
            values = series.values
            low = min(values)
            projected.append(
                ProjectionMonth(
                    year=year_month.year,
                    month=year_month.month,
                    label=f"{month_name[year_month.month]} {year_month.year}",
                    opening_pence=values[0],
                    closing_pence=values[-1],
                    low_pence=low,
                    low_day=values.index(low) + 1,
                    income_pence=summary.total_income.pence,
                    bank_bills_pence=summary.bank_bills.pence,
                    floor_pence=floor_pence,
                )
            )
        return projected
