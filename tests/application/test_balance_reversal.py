"""Tests for reversing applied balance amounts when items are deleted."""

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

_JULY = YearMonth(2026, 7)
_TODAY = date(2026, 7, 26)


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


def _log_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM balance_applied").fetchone()[0]


def _bill(name: str, pence: int, day) -> Bill:
    return Bill(
        id=0,
        name=name,
        amount=Amount(pence=pence),
        payment_method_id=1,
        category="utilities",
        bill_type="fixed",
        day_of_month=day,
        start_ym=YearMonth(2026, 1),
        end_ym=None,
    )


def _income(name: str, pence: int, day) -> IncomeSource:
    return IncomeSource(
        id=0, name=name, amount=Amount(pence=pence), is_reliable=True, day_of_month=day
    )


class TestDeleteReversal:
    def test_deleting_folded_bill_hands_amount_back(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, iso="2026-07-24")
        bill = budget_service.add_bill(bill=_bill("Water", 3000, 25))
        budget_service.apply_elapsed_bank_transactions(today=_TODAY)
        assert budget_service.get_bank_balance().pence == 7000
        budget_service.delete_bill(bill_id=bill.id)
        assert budget_service.get_bank_balance().pence == 10000
        assert _log_count(conn) == 0

    def test_deleting_folded_income_takes_amount_back(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, iso="2026-07-24")
        income = budget_service.add_income(income=_income("Salary", 200000, 25))
        budget_service.apply_elapsed_bank_transactions(today=_TODAY)
        assert budget_service.get_bank_balance().pence == 210000
        budget_service.delete_income(income_id=income.id)
        assert budget_service.get_bank_balance().pence == 10000
        assert _log_count(conn) == 0

    def test_deleting_applied_extra_income_takes_amount_back(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, iso="2026-07-24")
        extra = budget_service.add_income_month_extra(
            income=_income("Refund", 1500, 25), year_month=_JULY
        )
        budget_service.apply_elapsed_bank_transactions(today=_TODAY)
        assert budget_service.get_bank_balance().pence == 11500
        budget_service.delete_income_month_extra(extra_id=extra.id)
        assert budget_service.get_bank_balance().pence == 10000
        assert _log_count(conn) == 0

    def test_deleting_unapplied_item_leaves_balance_alone(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, iso="2026-07-26")
        bill = budget_service.add_bill(bill=_bill("Rent", 5000, 28))
        budget_service.delete_bill(bill_id=bill.id)
        assert budget_service.get_bank_balance().pence == 10000

    def test_manually_paid_bill_is_not_refunded_on_delete(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, iso="2026-07-26")
        bill = budget_service.add_bill(bill=_bill("Rent", 5000, 28))
        budget_service.mark_bill_paid_for_month(bill_id=bill.id, year_month=_JULY)
        budget_service.delete_bill(bill_id=bill.id)
        assert budget_service.get_bank_balance().pence == 10000

    def test_end_bill_refunds_only_removed_months(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=100000, iso="2026-05-20")
        bill = budget_service.add_bill(bill=_bill("Rent", 5000, 25))
        budget_service.apply_elapsed_bank_transactions(today=_TODAY)
        # Applied for May 25, Jun 25 and Jul 25: balance 100000 - 15000.
        assert budget_service.get_bank_balance().pence == 85000
        budget_service.end_bill(bill_id=bill.id, last_active_month=YearMonth(2026, 6))
        # July's application is handed back; May and June keep theirs.
        assert budget_service.get_bank_balance().pence == 90000
        assert _log_count(conn) == 2

    def test_manual_balance_set_supersedes_applied_amounts(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, iso="2026-07-24")
        bill = budget_service.add_bill(bill=_bill("Water", 3000, 25))
        budget_service.apply_elapsed_bank_transactions(today=_TODAY)
        budget_service.set_bank_balance(amount=Amount(pence=5000))
        assert _log_count(conn) == 0
        budget_service.delete_bill(bill_id=bill.id)
        assert budget_service.get_bank_balance().pence == 5000


class TestApplyNow:
    def test_apply_bill_now_deducts_marks_and_logs(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, iso="2026-07-26")
        bill = budget_service.add_bill(bill=_bill("Water", 3000, 26))
        budget_service.apply_bill_to_balance_now(bill=bill, year_month=_JULY)
        assert budget_service.get_bank_balance().pence == 7000
        summary = budget_service.get_month_summary(year_month=_JULY)
        assert all(b.paid_for_month for b in summary.bills)
        budget_service.delete_bill(bill_id=bill.id)
        assert budget_service.get_bank_balance().pence == 10000

    def test_apply_income_now_adds_marks_and_logs(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, iso="2026-07-26")
        income = budget_service.add_income(income=_income("Bonus", 4000, 26))
        budget_service.apply_income_to_balance_now(income=income, year_month=_JULY)
        assert budget_service.get_bank_balance().pence == 14000
        summary = budget_service.get_month_summary(year_month=_JULY)
        assert all(i.received_for_month for i in summary.income_sources)
        budget_service.delete_income(income_id=income.id)
        assert budget_service.get_bank_balance().pence == 10000

    def test_apply_extra_income_now_marks_extra_and_logs(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, iso="2026-07-26")
        extra = budget_service.add_income_month_extra(
            income=_income("Refund", 1500, 26), year_month=_JULY
        )
        budget_service.apply_income_to_balance_now(income=extra, year_month=_JULY)
        assert budget_service.get_bank_balance().pence == 11500
        extras = budget_service.income_repo.list_extras_for_month(year_month=_JULY)
        assert all(e.received_for_month for e in extras)
        budget_service.delete_income_month_extra(extra_id=extra.id)
        assert budget_service.get_bank_balance().pence == 10000


class TestReverseWithoutConnection:
    def test_none_connection_is_noop(self):
        from clear_budget.application.services._balance_application import (
            reverse_applied_for_item,
        )

        assert reverse_applied_for_item(None, item_type="bill", item_id=1) == 0


class TestResetClearsLog:
    def test_reset_all_data_clears_applied_log(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, iso="2026-07-24")
        budget_service.add_bill(bill=_bill("Water", 3000, 25))
        budget_service.apply_elapsed_bank_transactions(today=_TODAY)
        assert _log_count(conn) == 1
        budget_service.reset_all_data()
        assert _log_count(conn) == 0
