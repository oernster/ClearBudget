"""The overnight fold applies everything or nothing.

Each "paid" mark used to commit on its own while the balance was written once
at the end. Interrupted between the two, a bill stayed marked paid without its
amount ever leaving the balance; the next run skipped it as already applied,
so the user was shown the bill's amount more than they had, for good.

The marks, the applied-log rows and the balance now share one transaction.
These tests interrupt the fold at two points (after a mark; at the balance
write itself) and require that nothing was kept, then that a clean rerun lands
on the true figure.
"""

from datetime import date

import pytest

from clear_budget.application.services import _bank_transaction_fold
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
_OPENING_PENCE = 100000
_RENT_PENCE = 60000
_PAY_PENCE = 5000
_BASELINE = "2025-05-01"
_TODAY = date(2025, 5, 4)
_MAY = YearMonth(2025, 5)


class _Interrupted(Exception):
    """Stands in for the process stopping part way through the fold."""


@pytest.fixture()
def budget_service(tmp_path):
    db = Database(tmp_path / "fold.db")
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
    conn = db.conn
    for key, value in (
        ("bank_balance", str(_OPENING_PENCE)),
        ("bank_balance_date", _BASELINE),
    ):
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
    conn.commit()
    svc.add_bill(
        bill=Bill(
            id=0,
            name="Rent",
            amount=Amount(pence=_RENT_PENCE),
            payment_method_id=_BANK,
            category="housing",
            bill_type="fixed",
            day_of_month=2,
            start_ym=YearMonth(2025, 1),
            end_ym=None,
        )
    )
    svc.add_income(
        income=IncomeSource(
            id=0,
            name="Pay",
            amount=Amount(pence=_PAY_PENCE),
            is_reliable=True,
            day_of_month=3,
        )
    )
    yield svc
    db.close()


def _balance(conn) -> int:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'bank_balance'"
    ).fetchone()
    return int(row["value"])


def _baseline(conn) -> str:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'bank_balance_date'"
    ).fetchone()
    return row["value"]


def _applied_rows(conn) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM balance_applied").fetchone()["n"]


def _rent_paid(svc) -> bool:
    summary = svc.get_month_summary(year_month=_MAY)
    return next(b for b in summary.bills if b.name == "Rent").paid_for_month


def _assert_nothing_kept(svc) -> None:
    conn = svc.bill_repo.conn
    assert not _rent_paid(svc)
    assert _balance(conn) == _OPENING_PENCE
    assert _baseline(conn) == _BASELINE
    assert _applied_rows(conn) == 0


def _assert_rerun_is_true(svc) -> None:
    delta = svc.apply_elapsed_bank_transactions(today=_TODAY)
    assert delta == _PAY_PENCE - _RENT_PENCE
    assert _balance(svc.bill_repo.conn) == _OPENING_PENCE - _RENT_PENCE + _PAY_PENCE
    assert _rent_paid(svc)


class TestAnInterruptedFoldKeepsNothing:
    def test_stopped_after_the_rent_mark(self, budget_service):
        """The auditor's case: rent marked, then the run stops at the pay mark."""
        real_mark = budget_service.income_repo.mark_received_for_month

        def stop(**_kwargs):
            raise _Interrupted

        budget_service.income_repo.mark_received_for_month = stop
        with pytest.raises(_Interrupted):
            budget_service.apply_elapsed_bank_transactions(today=_TODAY)
        budget_service.income_repo.mark_received_for_month = real_mark

        _assert_nothing_kept(budget_service)
        _assert_rerun_is_true(budget_service)

    def test_stopped_at_the_balance_write(self, budget_service, monkeypatch):
        """Every mark and log row is written; the last step fails."""

        def stop(*_args, **_kwargs):
            raise _Interrupted

        monkeypatch.setattr(_bank_transaction_fold, "set_bank_balance_pence", stop)
        with pytest.raises(_Interrupted):
            budget_service.apply_elapsed_bank_transactions(today=_TODAY)
        monkeypatch.undo()

        _assert_nothing_kept(budget_service)
        _assert_rerun_is_true(budget_service)
