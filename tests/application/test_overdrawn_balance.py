"""An overdrawn bank balance must read back rather than crash the app.

The stored balance is a signed quantity: the midnight fold deducts a bank
bill from it whatever it holds, so a real overdraft is written as negative
pence. Reading it through the non-negative Amount raised at startup, while
the solvency view was built, so the account that went overdrawn could no
longer be opened at all.
"""

from datetime import date

import pytest

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)

_OVERDRAWN_PENCE = -12398
_TODAY = date(2026, 9, 17)


@pytest.fixture()
def budget_service(tmp_path):
    """BudgetService on a temp database whose stored balance is overdrawn."""
    db = Database(tmp_path / "test.db")
    db.connect()
    db.create_schema()
    for key, value in (
        ("bank_balance", str(_OVERDRAWN_PENCE)),
        ("bank_balance_day", str(_TODAY.day)),
        ("bank_balance_date", _TODAY.isoformat()),
    ):
        db.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
    db.conn.commit()
    yield BudgetService(
        bill_repo=SQLiteBillRepository(db.conn),
        income_repo=SQLiteIncomeSourceRepository(db.conn),
        payment_method_repo=SQLitePaymentMethodRepository(db.conn),
        month_generator=MonthGenerator(
            SQLiteBillRepository(db.conn), SQLiteIncomeSourceRepository(db.conn)
        ),
    )
    db.close()


def test_overdrawn_balance_reads_back_signed(budget_service):
    assert budget_service.get_bank_balance_pence() == _OVERDRAWN_PENCE


def test_solvency_calculates_for_an_overdrawn_account(budget_service):
    year_month = YearMonth(_TODAY.year, _TODAY.month)
    budget_service.calculate_solvency(year_month=year_month)


def test_projection_starts_from_the_overdrawn_balance(budget_service):
    year_month = YearMonth(_TODAY.year, _TODAY.month)
    pence = budget_service.get_projected_starting_balance_pence(
        year_month=year_month, today=_TODAY
    )
    assert pence == _OVERDRAWN_PENCE
