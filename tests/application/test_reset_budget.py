"""Tests for BudgetService.reset_all_data."""

import sqlite3
from pathlib import Path

import pytest

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)
from clear_budget.infrastructure.sqlite.database import Database


@pytest.fixture()
def budget_service(tmp_path):
    """BudgetService wired to a temp SQLite database."""
    db = Database(tmp_path / "test.db")
    db.connect()
    db.create_schema()
    bill_repo = SQLiteBillRepository(db.conn)
    income_repo = SQLiteIncomeSourceRepository(db.conn)
    pm_repo = SQLitePaymentMethodRepository(db.conn)
    generator = MonthGenerator(bill_repo, income_repo)
    svc = BudgetService(
        bill_repo=bill_repo,
        income_repo=income_repo,
        payment_method_repo=pm_repo,
        month_generator=generator,
    )
    yield svc
    db.close()


class TestResetAllData:
    """Test BudgetService.reset_all_data."""

    def test_reset_clears_bills(self, budget_service: BudgetService) -> None:
        from clear_budget.domain.entities.bill import Bill
        from clear_budget.domain.value_objects.amount import Amount
        from clear_budget.domain.value_objects.year_month import YearMonth

        bill = Bill(
            id=0,
            name="Rent",
            amount=Amount(pence=100000),
            payment_method_id=1,
            category="housing",
            bill_type="fixed",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
        )
        budget_service.add_bill(bill=bill)

        budget_service.reset_all_data()

        cursor = budget_service.bill_repo.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bills")
        assert cursor.fetchone()[0] == 0

    def test_reset_clears_income_sources(self, budget_service: BudgetService) -> None:
        from clear_budget.domain.entities.income_source import IncomeSource
        from clear_budget.domain.value_objects.amount import Amount

        income = IncomeSource(
            id=0,
            name="Salary",
            amount=Amount(pence=200000),
            is_reliable=True,
            day_of_month=1,
        )
        budget_service.add_income(income=income)

        budget_service.reset_all_data()

        cursor = budget_service.bill_repo.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM income_sources")
        assert cursor.fetchone()[0] == 0

    def test_reset_preserves_bank_account(self, budget_service: BudgetService) -> None:
        budget_service.reset_all_data()
        cursor = budget_service.bill_repo.conn.cursor()
        cursor.execute("SELECT id, name FROM payment_methods WHERE id = 1")
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "Bank Account"

    def test_reset_clears_credit_cards(self, budget_service: BudgetService) -> None:
        from clear_budget.domain.entities.credit_card import CreditCard
        from clear_budget.domain.value_objects.amount import Amount

        card = CreditCard(
            id=0,
            name="Visa",
            credit_limit=Amount(pence=500000),
            current_balance_used=Amount(pence=10000),
        )
        budget_service.payment_method_repo.add_credit_card(card=card)

        budget_service.reset_all_data()

        cursor = budget_service.bill_repo.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM credit_cards")
        assert cursor.fetchone()[0] == 0

    def test_reset_clears_settings(self, budget_service: BudgetService) -> None:
        from clear_budget.domain.value_objects.amount import Amount

        budget_service.set_bank_balance(amount=Amount(pence=99900))
        budget_service.reset_all_data()
        balance = budget_service.get_bank_balance()
        assert balance.pence == 0
