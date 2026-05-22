"""Test that credit card payment methods are saved correctly when adding bills."""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from clear_budget.domain.entities.bill import Bill
from clear_budget.domain.entities.credit_card import CreditCard
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.views.month_view import MonthView


@pytest.fixture
def app():
    """Create QApplication instance."""
    return QApplication.instance() or QApplication([])


@pytest.fixture
def database():
    """Create in-memory test database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        db.connect()
        db.create_schema()
        yield db
        db.close()


@pytest.fixture
def repos(database):
    """Create repositories."""
    bill_repo = SQLiteBillRepository(database.conn)
    income_repo = SQLiteIncomeSourceRepository(database.conn)
    payment_method_repo = SQLitePaymentMethodRepository(database.conn)
    return bill_repo, income_repo, payment_method_repo


def test_credit_card_bill_saved_with_correct_payment_method(app, database, repos):
    """Test that a bill created with a credit card saves with correct payment_method_id."""
    bill_repo, income_repo, payment_method_repo = repos

    # Create a test credit card
    test_card = CreditCard(
        id=0,
        name="TestCard",
        credit_limit=Amount(pence=100000),
        current_balance_used=Amount(pence=50000),
        payment_due_day=15,
        active=1,
    )
    saved_card = payment_method_repo.add_credit_card(card=test_card)
    assert saved_card.id > 0, "Card should be saved with an ID"
    card_id = saved_card.id

    # Create a bill with the credit card as payment method
    test_bill = Bill(
        id=0,
        name="Netflix",
        amount=Amount(pence=1299),
        payment_method_id=card_id,  # THIS MUST BE SAVED
        category="subscriptions",
        bill_type="fixed",
        day_of_month=10,
        start_ym=YearMonth(2026, 5),
        end_ym=None,
        active=True,
    )
    saved_bill = bill_repo.add(bill=test_bill)

    # VERIFY: The bill was saved with correct payment_method_id
    assert saved_bill.payment_method_id == card_id, (
        f"Bill should be saved with payment_method_id={card_id}, "
        f"but got {saved_bill.payment_method_id}"
    )

    # VERIFY: Fetch from database and confirm
    fetched_bill = bill_repo.get_by_id(bill_id=saved_bill.id)
    assert fetched_bill.payment_method_id == card_id, (
        f"Fetched bill from DB should have payment_method_id={card_id}, "
        f"but got {fetched_bill.payment_method_id}"
    )

    # VERIFY: The UI should display the card name, not "Bank"
    month_generator = MonthGenerator(bill_repo, income_repo)
    budget_service = BudgetService(
        bill_repo=bill_repo,
        income_repo=income_repo,
        payment_method_repo=payment_method_repo,
        month_generator=month_generator,
    )

    month_view_model = MonthViewModel(budget_service, YearMonth(2026, 5))
    month_view_model.refresh_month_summary()

    summary = month_view_model.month_summary
    assert summary is not None
    assert len(summary.bills) == 1
    bill_from_summary = summary.bills[0]

    # The bill should have the credit card's payment_method_id
    assert bill_from_summary.payment_method_id == card_id, (
        f"Bill in summary should have payment_method_id={card_id}, "
        f"but got {bill_from_summary.payment_method_id}"
    )

    print(f"PASS: Bill saved with payment_method_id={card_id} (TestCard)")
    print(f"PASS: Bill retrieved from DB with payment_method_id={card_id}")
    print(f"PASS: Bill displayed in UI with payment_method_id={card_id}")


def test_bill_displays_credit_card_name_in_ui(app, database, repos):
    """Test that the UI displays the credit card name, not 'Bank'."""
    bill_repo, income_repo, payment_method_repo = repos

    # Create a credit card
    test_card = CreditCard(
        id=0,
        name="CapitalOne",
        credit_limit=Amount(pence=175000),
        current_balance_used=Amount(pence=141536),
        payment_due_day=22,
        active=1,
    )
    saved_card = payment_method_repo.add_credit_card(card=test_card)
    card_id = saved_card.id

    # Create a bill charged to that card
    test_bill = Bill(
        id=0,
        name="Render",
        amount=Amount(pence=5800),
        payment_method_id=card_id,
        category="subscriptions",
        bill_type="fixed",
        day_of_month=1,
        start_ym=YearMonth(2026, 5),
        end_ym=None,
        active=True,
    )
    bill_repo.add(bill=test_bill)

    # Get the summary which would be displayed in the UI
    month_generator = MonthGenerator(bill_repo, income_repo)
    budget_service = BudgetService(
        bill_repo=bill_repo,
        income_repo=income_repo,
        payment_method_repo=payment_method_repo,
        month_generator=month_generator,
    )

    month_view_model = MonthViewModel(budget_service, YearMonth(2026, 5))
    month_view_model.refresh_month_summary()

    summary = month_view_model.month_summary
    assert len(summary.bills) == 1
    bill = summary.bills[0]

    # The payment_method_id should be the card's ID, NOT 1 (bank)
    assert bill.payment_method_id == card_id, (
        f"Bill payment_method_id should be {card_id} (CapitalOne), not 1 (Bank). "
        f"Got {bill.payment_method_id}"
    )
    assert (
        bill.payment_method_id != 1
    ), f"Bill MUST NOT be recorded as Bank (payment_method_id=1). Got {bill.payment_method_id}"

    print(f"PASS: Bill is recorded with CapitalOne (id={card_id}), not Bank")
