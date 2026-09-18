"""The Solvency page and the month graph must tell the same story, every month.

The Solvency page carries the current month's balance forward on its own
chain (the report's balance, then each month walked from it); the graph
carries it on another (each month opened from the projected start). Once they
disagreed by an income already marked Received, counted twice on one chain
only: the graph dipped into the red while Solvency called the same month
afloat. Nothing about that was specific to one month, so neither is this: it
checks every month for a year ahead from several dates, a year end included.
"""

from datetime import date

import pytest

from clear_budget.application.services._month_walk import walk_month
from clear_budget.domain.value_objects.year_month import YearMonth
from tests.application.test_month_graph_series import (  # noqa: F401 (fixture)
    _bill,
    _income,
    _seed_balance,
    budget_service,
)

_MONTHS_AHEAD = 12
_TODAYS = (
    date(2026, 1, 1),
    date(2026, 7, 31),
    date(2026, 9, 18),
    date(2026, 12, 10),
    date(2027, 2, 3),
)
_BALANCE = 50000
_FOOD = 30000


def _seed(svc, today: date) -> None:
    """A budget whose wages land early and whose rent is paid early.

    Both are marked this month, so both already sit inside the stored
    balance. The energy bill falls before the family money every month, so
    each month's low has a definite day on both chains.
    """
    _seed_balance(svc.bill_repo.conn, pence=_BALANCE, iso=today.isoformat())
    now = YearMonth(today.year, today.month)
    svc.add_bill(bill=_bill("Energy", 10000, 5))
    svc.add_bill(bill=_bill("Food", _FOOD, None))
    rent = svc.add_bill(bill=_bill("Rent", 250000, 21))
    svc.add_income(income=_income("Family", 60000, 15))
    wages = svc.add_income(income=_income("Wages", 300000, 20))
    svc.mark_income_received_for_month(income_id=wages.id, year_month=now)
    svc.mark_bill_paid_for_month(bill_id=rent.id, year_month=now)


@pytest.mark.parametrize("today", _TODAYS, ids=str)
def test_every_month_ahead_agrees_with_the_graph(budget_service, today):  # noqa: F811
    _seed(budget_service, today)
    month = YearMonth(today.year, today.month)
    opening = budget_service.calculate_solvency(year_month=month, today=today)
    opening = opening.balance_pence
    for _ in range(_MONTHS_AHEAD):
        month = month.next_month()
        summary = budget_service.get_month_summary(year_month=month)
        values = budget_service.get_bank_graph_series(
            year_month=month, summary=summary, today=today
        ).values
        graph_opening = budget_service.get_bank_month_opening_pence(
            year_month=month, summary=summary, today=today
        )
        walk = walk_month(opening, summary)
        low = min(values)
        assert opening == graph_opening, month
        assert (walk["min_balance"], walk["min_day"]) == (
            low,
            values.index(low) + 1,
        ), month
        assert walk["closing"] == values[-1], month
        report = budget_service.calculate_solvency(year_month=month, today=today)
        assert report.balance_pence == values[-1], month
        opening = walk["closing"]


def test_received_income_is_not_carried_forward(budget_service):  # noqa: F811
    """Worked by hand: on the 18th of a 30-day month the wages are received and
    the rent paid, the energy bill is overdue (presumed inside the typed
    balance) and the family money landed on the 15th. What still has to leave
    is food for the 12 days left, so next month opens at the balance less
    that share of it and nothing more."""
    today = date(2026, 9, 18)
    _seed(budget_service, today)
    report = budget_service.calculate_solvency(
        year_month=YearMonth(2026, 9), today=today
    )
    assert report.balance_pence == _BALANCE - _FOOD * 12 // 30
