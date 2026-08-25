"""Tests for the recommendations adapter and its buffer setting.

Real SQLite throughout, because the mapping under test is the one the stored
months actually produce: card bills must never reach the engine, an undated
item must never be offered as movable and a day-fixed flag must survive the
trip from the repository to the plan.
"""

from datetime import date

import pytest

from clear_budget.application.services._overdraft_projection import (
    _UNDATED_BILL_DAY,
)
from clear_budget.application.services._recommendation_operations import (
    _planned_month,
)
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.services.recommendations import KIND_BILL, KIND_INCOME
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

_TODAY = date(2026, 7, 26)
_AUGUST = YearMonth(2026, 8)
_SEPTEMBER = YearMonth(2026, 9)


@pytest.fixture()
def budget_service(tmp_path):
    """BudgetService wired to a temp SQLite database."""
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


def _seed_balance(conn, *, pence: int, iso: str) -> None:
    day = date.fromisoformat(iso).day
    for key, value in (
        ("bank_balance", str(pence)),
        ("bank_balance_day", str(day)),
        ("bank_balance_date", iso),
    ):
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
    conn.commit()


def _bill(
    name: str, pence: int, day, *, method: int = 1, day_fixed: bool = False
) -> Bill:
    return Bill(
        id=0,
        name=name,
        amount=Amount(pence=pence),
        payment_method_id=method,
        category="utilities",
        bill_type="fixed",
        day_of_month=day,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
        target_card_id=None,
        day_fixed=day_fixed,
    )


def _income(name: str, pence: int, day, *, day_fixed: bool = False) -> IncomeSource:
    return IncomeSource(
        id=0,
        name=name,
        amount=Amount(pence=pence),
        is_reliable=True,
        day_of_month=day,
        day_fixed=day_fixed,
    )


class TestMapping:
    def test_stored_months_map_to_the_engine_plan(self, budget_service):
        budget_service.add_bill(bill=_bill("Rent", 80000, 10))
        budget_service.add_bill(bill=_bill("Locked", 5000, 5, day_fixed=True))
        budget_service.add_bill(bill=_bill("Undated", 3000, None))
        budget_service.add_bill(bill=_bill("CardSub", 1500, 12, method=2))
        budget_service.add_income(income=_income("Pay", 120000, 25))
        budget_service.add_income(income=_income("UC", 40000, 20, day_fixed=True))

        summary = budget_service.get_month_summary(year_month=_AUGUST)
        plan = _planned_month(summary, 2026, 8)
        assert (plan.year, plan.month, plan.days) == (2026, 8, 31)
        by_name = {item.name: item for item in plan.items}

        # Card bills never reach the engine: retiming a card payment cannot
        # move money in the bank month.
        assert "CardSub" not in by_name

        rent = by_name["Rent"]
        assert (rent.kind, rent.day, rent.amount_pence, rent.movable) == (
            KIND_BILL,
            10,
            -80000,
            True,
        )
        # The day-fixed flag records the exception: present, dated, immovable.
        assert by_name["Locked"].movable is False
        # An undated bill takes the projection's day and is never movable.
        undated = by_name["Undated"]
        assert (undated.day, undated.movable) == (_UNDATED_BILL_DAY, False)

        pay = by_name["Pay"]
        assert (pay.kind, pay.day, pay.amount_pence, pay.movable) == (
            KIND_INCOME,
            25,
            120000,
            True,
        )
        assert by_name["UC"].movable is False

        # Income listed before bills, carrying the shared-day ordering rule.
        kinds = [item.kind for item in plan.items]
        assert kinds == sorted(kinds, key=lambda k: k != KIND_INCOME)


class TestGetRecommendations:
    def test_horizon_starts_the_month_after_today(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=100000, iso="2026-07-26")
        budget_service.set_sustainable_window_months(months=2)
        budget_service.add_bill(bill=_bill("Rent", 50000, 10))
        budget_service.add_income(income=_income("Pay", 60000, 20))

        result, horizon = budget_service.get_recommendations(today=_TODAY)
        assert horizon == (_AUGUST, _SEPTEMBER)
        assert [(m.year, m.month) for m in result.outlook] == [(2026, 8), (2026, 9)]

    def test_enabled_buffer_raises_the_target(self, budget_service):
        _seed_balance(budget_service.bill_repo.conn, pence=0, iso="2026-07-26")
        budget_service.set_sustainable_window_months(months=1)
        budget_service.add_bill(bill=_bill("Rent", 50000, 10, day_fixed=True))

        bare, _ = budget_service.get_recommendations(today=_TODAY)
        budget_service.set_recommendation_buffer(
            enabled=True, amount=Amount(pence=10000)
        )
        buffered, _ = budget_service.get_recommendations(today=_TODAY)
        (bare_ask,) = bare.asks
        (buffered_ask,) = buffered.asks
        # The same month asks for exactly the buffer more when it is enabled.
        assert buffered_ask.amount_pence - bare_ask.amount_pence == 10000


class TestBufferSetting:
    def test_defaults_to_disabled_and_zero(self, budget_service):
        assert budget_service.get_recommendation_buffer() == (False, Amount(pence=0))

    def test_round_trips_and_survives_disabling(self, budget_service):
        budget_service.set_recommendation_buffer(
            enabled=True, amount=Amount(pence=12345)
        )
        assert budget_service.get_recommendation_buffer() == (
            True,
            Amount(pence=12345),
        )
        # Disabling keeps the amount, so re-enabling restores the same figure.
        budget_service.set_recommendation_buffer(
            enabled=False, amount=Amount(pence=12345)
        )
        assert budget_service.get_recommendation_buffer() == (
            False,
            Amount(pence=12345),
        )
