"""An income you have ended stays ended, even under the repeat assumption.

Every forward projection assumes the income entered for this month arrives
again in each later month with no entry of that name. That rule exists to
cover an absence of DATA: ad hoc money typed in only where it has already
happened. It must not cover a deliberate ending.

The two features collide by construction. A recurring income given a final
month is absent from every month after it, which is exactly the shape the
repeat rule fills. Left alone it puts the income straight back, so ending an
income does not lower the spendable figure, which is precisely when the
figure must fall. `_missing_from` therefore tests `is_active_in_month` on the
target month as well as matching by name.

These run against a real SQLite database, because an income's month bounds
are a storage fact.
"""

from datetime import date

import pytest

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

_TODAY = date(2026, 7, 1)
_JULY = YearMonth(2026, 7)
_AUGUST = YearMonth(2026, 8)
_END_OF_JULY = date(2026, 7, 31)
_END_OF_AUGUST = date(2026, 8, 31)
_RENT_PENCE = 130000
_SALARY_PENCE = 100000


@pytest.fixture()
def service(tmp_path):
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


def _seed(service) -> IncomeSource:
    """Rent every month plus one recurring salary, ready to be ended."""
    conn = service.bill_repo.conn
    for key, value in (
        ("bank_balance", "0"),
        ("bank_balance_day", "1"),
        ("bank_balance_date", "2026-07-01"),
    ):
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
    conn.commit()
    service.set_safe_to_spend_floor(amount=Amount(pence=0))
    service.add_bill(
        bill=Bill(
            id=0,
            name="Rent",
            amount=Amount(pence=_RENT_PENCE),
            payment_method_id=1,
            category="utilities",
            bill_type="fixed",
            day_of_month=5,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
            target_card_id=None,
        )
    )
    return service.add_income(
        income=IncomeSource(
            id=0,
            name="Salary",
            amount=Amount(pence=_SALARY_PENCE),
            is_reliable=True,
            day_of_month=10,
        )
    )


def _august_movement(service) -> int:
    """What August does to the balance, from its opening to its close."""
    by_day = {
        d.day: d.balance_pence for d in service._build_safe_to_spend_inputs(_TODAY)
    }
    return by_day[_END_OF_AUGUST] - by_day[_END_OF_JULY]


class TestTheProjection:
    def test_a_live_income_is_repeated_into_a_later_month(self, service):
        """The control, so the test below cannot pass by the rule never firing."""
        _seed(service)
        assert _august_movement(service) == _SALARY_PENCE - _RENT_PENCE

    def test_an_ended_income_is_not_repeated_into_a_later_month(self, service):
        persisted = _seed(service)
        service.end_income(income_id=persisted.id, last_active_month=_JULY)
        # August must show the rent and no salary at all.
        assert _august_movement(service) == -_RENT_PENCE


class TestWhatTheAssumptionNames:
    def test_an_ended_income_is_not_named_as_money_still_to_arrive(self, service):
        persisted = _seed(service)
        service.end_income(income_id=persisted.id, last_active_month=_JULY)
        expected = service.get_assumed_expectations(today=_TODAY)
        assert "Salary" not in [source.name for _, source in expected]

    def test_an_ended_income_is_absent_from_a_later_assumed_summary(self, service):
        persisted = _seed(service)
        service.end_income(income_id=persisted.id, last_active_month=_JULY)
        assumed = service.get_assumed_month_summary(year_month=_AUGUST, today=_TODAY)
        assert assumed.total_income.pence == 0
