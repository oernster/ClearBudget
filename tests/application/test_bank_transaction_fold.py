"""Tests for the elapsed bank-transaction fold and balance adjustment."""

from datetime import date

import pytest

from clear_budget.application.services._bank_transaction_fold import (
    apply_elapsed_bank_transactions,
    resolve_baseline_date,
)
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
_CARD = 2


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


def _seed_balance(conn, *, pence: int, day: int = 0, iso: str | None = None) -> None:
    cursor = conn.cursor()
    rows = [("bank_balance", str(pence)), ("bank_balance_day", str(day))]
    if iso is not None:
        rows.append(("bank_balance_date", iso))
    for key, value in rows:
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
    conn.commit()


def _setting(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _bill(name: str, pence: int, day, method: int = _BANK) -> Bill:
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
    )


def _income(name: str, pence: int, day) -> IncomeSource:
    return IncomeSource(
        id=0, name=name, amount=Amount(pence=pence), is_reliable=True, day_of_month=day
    )


class TestResolveBaselineDate:
    def test_iso_value_wins(self):
        baseline = resolve_baseline_date(
            iso_value="2026-07-20", balance_day=3, today=date(2026, 7, 26)
        )
        assert baseline == date(2026, 7, 20)

    def test_never_set_returns_none(self):
        assert (
            resolve_baseline_date(
                iso_value=None, balance_day=0, today=date(2026, 7, 26)
            )
            is None
        )

    def test_legacy_day_this_month(self):
        baseline = resolve_baseline_date(
            iso_value=None, balance_day=20, today=date(2026, 7, 26)
        )
        assert baseline == date(2026, 7, 20)

    def test_legacy_day_previous_month_clamped(self):
        baseline = resolve_baseline_date(
            iso_value=None, balance_day=31, today=date(2026, 3, 5)
        )
        assert baseline == date(2026, 2, 28)


class TestApplyElapsedBankTransactions:
    def test_no_baseline_is_noop(self, budget_service):
        conn = budget_service.bill_repo.conn
        budget_service.add_bill(bill=_bill("Rent", 5000, 25))
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        assert delta == 0
        assert _setting(conn, "bank_balance") is None

    def test_baseline_today_is_noop(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=26, iso="2026-07-26")
        budget_service.add_bill(bill=_bill("Rent", 5000, 26))
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        assert delta == 0
        assert _setting(conn, "bank_balance") == "10000"

    def test_baseline_in_future_is_noop(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=27, iso="2026-07-27")
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        assert delta == 0

    def test_bank_bill_due_yesterday_is_folded_and_marked(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=24, iso="2026-07-24")
        budget_service.add_bill(bill=_bill("Water", 3000, 25))
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        assert delta == -3000
        assert _setting(conn, "bank_balance") == "7000"
        assert _setting(conn, "bank_balance_day") == "26"
        assert _setting(conn, "bank_balance_date") == "2026-07-26"
        summary = budget_service.get_month_summary(year_month=YearMonth(2026, 7))
        assert all(b.paid_for_month for b in summary.bills)

    def test_second_run_same_day_is_idempotent(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=24, iso="2026-07-24")
        budget_service.add_bill(bill=_bill("Water", 3000, 25))
        budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        assert delta == 0
        assert _setting(conn, "bank_balance") == "7000"

    def test_card_bill_is_ignored(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=24, iso="2026-07-24")
        budget_service.add_bill(bill=_bill("Card sub", 3000, 25, method=_CARD))
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        assert delta == 0
        summary = budget_service.get_month_summary(year_month=YearMonth(2026, 7))
        assert not any(b.paid_for_month for b in summary.bills)

    def test_already_paid_bill_is_ignored(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=24, iso="2026-07-24")
        bill = budget_service.add_bill(bill=_bill("Water", 3000, 25))
        budget_service.mark_bill_paid_for_month(
            bill_id=bill.id, year_month=YearMonth(2026, 7)
        )
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        assert delta == 0

    def test_dateless_items_are_ignored(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=24, iso="2026-07-24")
        budget_service.add_bill(bill=_bill("Groceries", 4000, None))
        budget_service.add_income(income=_income("Odd jobs", 2000, None))
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        assert delta == 0

    def test_income_due_yesterday_is_folded_and_marked(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=24, iso="2026-07-24")
        budget_service.add_income(income=_income("Salary", 200000, 25))
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        assert delta == 200000
        assert _setting(conn, "bank_balance") == "210000"
        summary = budget_service.get_month_summary(year_month=YearMonth(2026, 7))
        assert all(i.received_for_month for i in summary.income_sources)

    def test_received_income_is_ignored(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=24, iso="2026-07-24")
        income = budget_service.add_income(income=_income("Salary", 200000, 25))
        budget_service.mark_income_received_for_month(
            income_id=income.id, year_month=YearMonth(2026, 7)
        )
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        assert delta == 0

    def test_month_extra_income_is_folded_and_marked(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=24, iso="2026-07-24")
        budget_service.add_income_month_extra(
            income=_income("Refund", 1500, 25), year_month=YearMonth(2026, 7)
        )
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        assert delta == 1500
        extras = budget_service.income_repo.list_extras_for_month(
            year_month=YearMonth(2026, 7)
        )
        assert all(e.received_for_month for e in extras)

    def test_due_day_clamped_to_short_month_end(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=29, iso="2026-04-29")
        budget_service.add_bill(bill=_bill("Rent", 5000, 31))
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 5, 1))
        assert delta == -5000

    def test_multi_month_gap_folds_each_month(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=100000, day=20, iso="2026-05-20")
        budget_service.add_bill(bill=_bill("Rent", 5000, 25))
        budget_service.add_income(income=_income("Salary", 20000, 1))
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 5))
        # Rent falls due May 25 and Jun 25; salary arrives Jun 1 and Jul 1.
        assert delta == -5000 - 5000 + 20000 + 20000
        assert _setting(conn, "bank_balance") == str(100000 + delta)

    def test_legacy_day_only_baseline_folds(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=24)
        budget_service.add_bill(bill=_bill("Water", 3000, 25))
        delta = budget_service.apply_elapsed_bank_transactions(today=date(2026, 7, 26))
        assert delta == -3000
        assert _setting(conn, "bank_balance_date") == "2026-07-26"

    def test_none_conn_is_noop(self):
        delta = apply_elapsed_bank_transactions(
            conn=None,
            get_month_summary=None,
            mark_bill_paid=None,
            mark_income_received=None,
            mark_income_extra_received=None,
            today=date(2026, 7, 26),
        )
        assert delta == 0

    def test_default_today_argument(self, budget_service):
        delta = budget_service.apply_elapsed_bank_transactions()
        assert delta == 0


class TestAdjustBankBalance:
    def test_applies_signed_delta_and_stamps_today(self, budget_service):
        conn = budget_service.bill_repo.conn
        _seed_balance(conn, pence=10000, day=1, iso="2026-07-01")
        budget_service.adjust_bank_balance(delta_pence=-2500)
        assert _setting(conn, "bank_balance") == "7500"
        stamp = date.today()
        assert _setting(conn, "bank_balance_date") == stamp.isoformat()

    def test_from_unset_balance(self, budget_service):
        conn = budget_service.bill_repo.conn
        budget_service.adjust_bank_balance(delta_pence=4000)
        assert _setting(conn, "bank_balance") == "4000"
