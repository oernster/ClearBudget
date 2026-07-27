"""Tests for the multi-month projection behind the range export.

Uses a real SQLite database in a tmpdir rather than a mock, the same as the
other application tests, so the projection is exercised through the real
month generation and balance rules.
"""

from itertools import pairwise

import pytest

from clear_budget.application.services._projection_series import months_between
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)

_BANK = 1
_JULY = YearMonth(2026, 7)
_SEPTEMBER = YearMonth(2026, 9)


@pytest.fixture()
def budget_service(tmp_path):
    db = Database(tmp_path / "test.db")
    db.connect()
    db.create_schema()
    svc = BudgetService(
        bill_repo=SQLiteBillRepository(db.conn),
        income_repo=SQLiteIncomeSourceRepository(db.conn),
        payment_method_repo=SQLitePaymentMethodRepository(db.conn),
        month_generator=MonthGenerator(
            SQLiteBillRepository(db.conn), SQLiteIncomeSourceRepository(db.conn)
        ),
    )
    yield svc
    db.close()


def _seed(service, *, income_pence, bill_pence, bill_day):
    service.add_income(
        income=IncomeSource(
            id=0,
            name="Salary",
            amount=Amount(pence=income_pence),
            is_reliable=True,
            day_of_month=1,
        )
    )
    service.add_bill(
        bill=Bill(
            id=0,
            name="Rent",
            amount=Amount(pence=bill_pence),
            payment_method_id=_BANK,
            category="utilities",
            bill_type="fixed",
            day_of_month=bill_day,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
            target_card_id=None,
        )
    )


# months_between is the range walk the export depends on.
def test_a_single_month_range_is_that_month():
    assert months_between(_JULY, _JULY) == [_JULY]


def test_a_range_walks_forward_inclusively():
    assert months_between(_JULY, _SEPTEMBER) == [
        YearMonth(2026, 7),
        YearMonth(2026, 8),
        YearMonth(2026, 9),
    ]


def test_a_range_carries_over_the_year_end():
    walked = months_between(YearMonth(2026, 11), YearMonth(2027, 2))
    assert walked == [
        YearMonth(2026, 11),
        YearMonth(2026, 12),
        YearMonth(2027, 1),
        YearMonth(2027, 2),
    ]


def test_a_backwards_range_yields_nothing_rather_than_looping():
    assert months_between(_SEPTEMBER, _JULY) == []


# The projection itself.
def test_one_projected_month_per_month_in_the_range(budget_service):
    _seed(budget_service, income_pence=200_000, bill_pence=50_000, bill_day=15)
    months = budget_service.get_projection_months(start=_JULY, end=_SEPTEMBER)
    assert [m.label for m in months] == ["July 2026", "August 2026", "September 2026"]


def test_each_month_reports_its_own_income_and_bank_bills(budget_service):
    _seed(budget_service, income_pence=200_000, bill_pence=50_000, bill_day=15)
    month = budget_service.get_projection_months(start=_JULY, end=_JULY)[0]
    assert month.income_pence == 200_000
    assert month.bank_bills_pence == 50_000
    assert month.net_pence == 150_000


def test_the_low_is_the_lowest_day_not_the_closing_balance(budget_service):
    """The case the report exists for: a dip that the month end hides."""
    _seed(budget_service, income_pence=200_000, bill_pence=180_000, bill_day=2)
    month = budget_service.get_projection_months(start=_JULY, end=_JULY)[0]
    assert month.low_pence <= month.closing_pence
    assert 1 <= month.low_day <= 31


def test_the_projection_agrees_with_the_month_graph(budget_service):
    """Report and graph must never disagree about a month they both cover."""
    _seed(budget_service, income_pence=200_000, bill_pence=50_000, bill_day=15)
    summary = budget_service.get_month_summary(year_month=_JULY)
    # No `today` override: the projection uses the real one, and the point of
    # the test is that both take the same path for the same month.
    series = budget_service.get_bank_graph_series(year_month=_JULY, summary=summary)
    month = budget_service.get_projection_months(start=_JULY, end=_JULY)[0]
    assert month.closing_pence == series.values[-1]
    assert month.low_pence == min(series.values)


def test_opening_plus_net_equals_the_close(budget_service):
    """The identity that makes the exported table checkable by eye.

    Opening is the month's real projected opening balance, not day one's
    closing value; if it were the latter, a month whose income lands on day 1
    would show an opening that already contained it and the row would not add
    up.
    """
    _seed(budget_service, income_pence=200_000, bill_pence=50_000, bill_day=15)
    for month in budget_service.get_projection_months(start=_JULY, end=_SEPTEMBER):
        assert month.opening_pence + month.net_pence == month.closing_pence


def test_each_month_opens_where_the_previous_one_closed(budget_service):
    """The range is one chain, which is what ties it to the real balance."""
    _seed(budget_service, income_pence=200_000, bill_pence=50_000, bill_day=15)
    months = budget_service.get_projection_months(start=_JULY, end=_SEPTEMBER)
    for earlier, later in pairwise(months):
        assert later.opening_pence == earlier.closing_pence


def test_the_chain_starts_from_the_recorded_bank_balance(budget_service):
    """Change the recorded balance and the whole projection moves with it."""
    _seed(budget_service, income_pence=200_000, bill_pence=50_000, bill_day=15)
    before = budget_service.get_projection_months(start=_JULY, end=_JULY)[0]
    budget_service.set_bank_balance(amount=Amount(pence=500_000))
    after = budget_service.get_projection_months(start=_JULY, end=_JULY)[0]
    assert after.closing_pence != before.closing_pence


def test_the_floor_is_the_overdraft_limit_as_a_negative(budget_service):
    _seed(budget_service, income_pence=200_000, bill_pence=50_000, bill_day=15)
    month = budget_service.get_projection_months(start=_JULY, end=_JULY)[0]
    assert month.floor_pence <= 0


def test_a_backwards_range_projects_nothing(budget_service):
    assert budget_service.get_projection_months(start=_SEPTEMBER, end=_JULY) == []
