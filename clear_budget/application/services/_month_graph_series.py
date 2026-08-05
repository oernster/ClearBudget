"""Month graph data series for BudgetService - bank and card day-by-day balances.

Feeds the nav-tray month graph. The bank series traces the projected bank
balance at the end of each day of the viewed month; the card series traces
each active card's balance the same way. Both reuse the projection rules the
rest of the app runs on (undated income lands day 1, undated bank bills near
month end, undated card bills accrue evenly).
"""

from datetime import date

from clear_budget.application.dto.graph_series import GraphSeries
from clear_budget.application.services._overdraft_projection import _month_events
from clear_budget.domain.services._card_live_projection import (
    anchored_month_opening_pence,
    month_to_date_net_pence,
)
from clear_budget.domain.services._prorating import days_in_month
from clear_budget.domain.value_objects.year_month import YearMonth

_BANK_SERIES_LABEL = "Bank balance"


class GraphSeriesMixin:
    """Month graph series providers for BudgetService."""

    __slots__ = ()

    @staticmethod
    def _per_day_pence(summary, days: int) -> list[int]:
        """Net movement on each day of the month, indexed 1..days."""
        per_day = [0] * (days + 1)
        for event in _month_events(summary):
            per_day[min(event.day_of_month, days)] += event.amount_pence
        return per_day

    def get_bank_month_opening_pence(
        self, *, year_month: YearMonth, summary, today: date | None = None
    ) -> int:
        """The balance the month's day-by-day projection starts from.

        For the current month this is anchored on the stored balance, wound
        back over whatever has already been applied this month, so the
        trajectory passes through today's real figure on today's date. Other
        months start from the projected opening.

        Public because the multi-month projection reports this number, and it
        MUST be the one the graph actually starts from: computing an opening
        separately let the two drift, so a report could show an opening that
        did not add up to its own closing balance.
        """
        today = today or date.today()  # noqa: DTZ011 (naive local dates)
        days = days_in_month(year_month.year, year_month.month)
        if year_month != YearMonth(today.year, today.month):
            return self.get_projected_starting_balance_pence(
                year_month=year_month, today=today
            )
        per_day = self._per_day_pence(summary, days)
        elapsed = sum(per_day[1 : min(today.day, days) + 1])
        return self.get_bank_balance().pence - elapsed

    def get_bank_graph_series(
        self, *, year_month: YearMonth, summary, today: date | None = None
    ) -> GraphSeries:
        """Day-end projected bank balance for each day of year_month."""
        days = days_in_month(year_month.year, year_month.month)
        per_day = self._per_day_pence(summary, days)
        running = self.get_bank_month_opening_pence(
            year_month=year_month, summary=summary, today=today
        )
        values = []
        for day in range(1, days + 1):
            running += per_day[day]
            values.append(running)
        return GraphSeries(label=_BANK_SERIES_LABEL, values=tuple(values))

    def get_card_graph_series(self, *, year_month: YearMonth) -> list[GraphSeries]:
        """One day-end balance series per active card for year_month."""
        summary = self.get_month_summary(year_month=year_month)
        bills = list(summary.bills)
        days = days_in_month(year_month.year, year_month.month)
        series = []
        for card in self.get_credit_cards():
            opening = anchored_month_opening_pence(
                card=card,
                bills=bills,
                year=year_month.year,
                month=year_month.month,
            )
            values = tuple(
                max(
                    0,
                    opening
                    + month_to_date_net_pence(
                        card=card,
                        bills=bills,
                        today=date(year_month.year, year_month.month, day),
                    ),
                )
                for day in range(1, days + 1)
            )
            series.append(GraphSeries(label=card.name, values=values))
        return series
