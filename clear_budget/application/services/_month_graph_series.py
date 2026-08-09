"""Month graph data series for BudgetService - bank and card day-by-day balances.

Feeds the nav-tray month graph. The bank series traces the projected bank
balance at the end of each day of the viewed month; the card series traces
each active card's balance the same way. Both reuse the projection rules the
rest of the app runs on (undated income lands day 1, undated bank bills near
month end, undated card bills accrue evenly).
"""

from datetime import date

from clear_budget.application.dto.graph_series import GraphSeries
from clear_budget.application.services._overdraft_projection import (
    _BANK_PAYMENT_METHOD_ID,
    _UNDATED_BILL_DAY,
    _UNDATED_INCOME_DAY,
)
from clear_budget.domain.services._card_live_projection import (
    anchored_month_opening_pence,
    month_to_date_net_pence,
)
from clear_budget.domain.services._prorating import days_in_month
from clear_budget.domain.value_objects.year_month import YearMonth

_BANK_SERIES_LABEL = "Bank balance"


def _event_counts(day: int, happened: bool, today_day: int | None) -> bool:
    """Whether an event belongs on the month's timeline.

    Outside the current month (``today_day`` is None) every event counts.
    Inside it, an event already actioned (a bill marked Paid, an income
    marked Received) is part of the stored balance the projection anchors
    on, so it may only appear on a day already reached: charging a bill paid
    early on its future due day again would double-count money that has
    already left the account. A still-pending event belongs to the future:
    an overdue one that never happened would otherwise draw a historical
    drop the account never took, exactly as the projected-balance rule in
    _balance_projection already treats it.
    """
    if today_day is None:
        return True
    if happened:
        return day <= today_day
    return day >= today_day


class GraphSeriesMixin:
    """Month graph series providers for BudgetService."""

    __slots__ = ()

    @staticmethod
    def _per_day_pence(summary, days: int, today_day: int | None = None) -> list[int]:
        """Net movement on each day of the month, indexed 1..days.

        With ``today_day`` given (the viewed month is the current one), the
        Paid and Received flags decide whether each event has already
        happened or is still to come; see _event_counts.
        """
        per_day = [0] * (days + 1)
        for inc in summary.income_sources:
            day = inc.day_of_month or _UNDATED_INCOME_DAY
            if _event_counts(day, inc.received_for_month, today_day):
                per_day[min(day, days)] += inc.amount.pence
        for bill in summary.bills:
            if bill.payment_method_id != _BANK_PAYMENT_METHOD_ID:
                continue
            day = bill.day_of_month or _UNDATED_BILL_DAY
            if _event_counts(day, bill.paid_for_month, today_day):
                per_day[min(day, days)] -= bill.amount.pence
        return per_day

    @staticmethod
    def _today_day_in(year_month: YearMonth, today: date) -> int | None:
        """Today's day number when year_month is the current month, else None."""
        if year_month == YearMonth(today.year, today.month):
            return today.day
        return None

    def get_bank_month_opening_pence(
        self, *, year_month: YearMonth, summary, today: date | None = None
    ) -> int:
        """The balance the month's day-by-day projection starts from.

        For the current month this is anchored on the stored balance, wound
        back over whatever has already been applied this month, so the
        trajectory passes through today's real figure on today's date. Other
        months start from the projected opening.

        Public because the multi-month projection reports this number and it
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
        per_day = self._per_day_pence(summary, days, today_day=today.day)
        elapsed = sum(per_day[1 : min(today.day, days) + 1])
        return self.get_bank_balance().pence - elapsed

    def get_bank_graph_series(
        self, *, year_month: YearMonth, summary, today: date | None = None
    ) -> GraphSeries:
        """Day-end projected bank balance for each day of year_month."""
        today = today or date.today()  # noqa: DTZ011 (naive local dates)
        days = days_in_month(year_month.year, year_month.month)
        per_day = self._per_day_pence(
            summary, days, today_day=self._today_day_in(year_month, today)
        )
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
