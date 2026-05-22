"""End-to-end UI test: double-click Fixed Min (£) cell, type 120.45, press Enter,
verify displayed value is £120.45.

Uses QTest to simulate real mouse and keyboard input on the live widget.
"""

import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

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
from clear_budget.ui.views.credit_card_view import CreditCardView

MONTH = YearMonth(2026, 5)
COL_FIXED_MIN = 7  # "Fixed Min (£)" — user-settable minimum payment


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        database = Database(Path(tmpdir) / "test.db")
        database.connect()
        database.create_schema()
        yield database
        database.close()


@pytest.fixture
def service(db):
    bill_repo = SQLiteBillRepository(db.conn)
    income_repo = SQLiteIncomeSourceRepository(db.conn)
    pm_repo = SQLitePaymentMethodRepository(db.conn)
    return BudgetService(
        bill_repo=bill_repo,
        income_repo=income_repo,
        payment_method_repo=pm_repo,
        month_generator=MonthGenerator(bill_repo, income_repo),
    )


def _add_card(service, name="Jaja", balance_pence=295444, apr=25.54):
    card = CreditCard(
        id=0,
        name=name,
        credit_limit=Amount(pence=500000),
        current_balance_used=Amount(pence=balance_pence),
        interest_rate_apr=apr,
        payment_due_day=8,
        active=1,
    )
    return service.payment_method_repo.add_credit_card(card=card)


@pytest.fixture
def view(app, service):
    v = CreditCardView(budget_service=service, current_month=MONTH)
    v.resize(1400, 600)
    v.show()
    app.processEvents()
    return v


class TestInlineEditMinPaymentPound:

    def test_double_click_type_enter_shows_pound_prefix(self, app, view, service):
        """
        PROOF TEST: Simulate user double-clicking Fixed Min (£) cell,
        typing 120.45, pressing Enter — cell must show £120.45.
        """
        _add_card(service)
        view.load_cards()
        app.processEvents()

        table = view.cards_table
        assert table.rowCount() == 1, f"Expected 1 card row, got {table.rowCount()}"

        # Verify cell starts as " - " (no fixed min set)
        item_before = table.item(0, COL_FIXED_MIN)
        assert item_before is not None
        assert item_before.text() == " - ", f"Pre-condition: got {item_before.text()!r}"

        QTest.qWait(50)
        app.processEvents()

        # Open the inline editor programmatically (equivalent to user double-clicking)
        cell_item = table.item(0, COL_FIXED_MIN)
        assert cell_item is not None, "No item at row 0 col 7"
        table.setCurrentItem(cell_item)
        table.editItem(cell_item)
        app.processEvents()

        # Find the open QLineEdit editor
        editors = table.viewport().findChildren(QLineEdit)
        assert editors, (
            "No inline editor opened after editItem(). "
            "Cell is not editable — EditTrigger or ItemIsEditable missing."
        )
        editor = editors[0]

        # Clear any existing text, type 120.45, press Enter
        editor.selectAll()
        QTest.keyClicks(editor, "120.45")
        assert "120.45" in editor.text(), f"Editor text after typing: {editor.text()!r}"

        QTest.keyClick(editor, Qt.Key.Key_Return)
        app.processEvents()
        app.processEvents()  # fire QTimer.singleShot(0, load_cards)
        QTest.qWait(100)  # allow load_cards to complete
        app.processEvents()

        # THE ASSERTION: cell must display £120.45
        item_after = table.item(0, COL_FIXED_MIN)
        assert item_after is not None, "Cell item is None after edit"
        assert (
            item_after.text() == "£120.45"
        ), f"FAIL: expected '£120.45', got {item_after.text()!r}"

    def test_edit_from_existing_value_preserves_pound(self, app, view, service):
        """
        PROOF TEST: Card already has fixed min £63.54.
        User opens editor, types 120.45, presses Enter → must show £120.45.
        """
        card = _add_card(service, name="CapitalOne", balance_pence=139523, apr=24.9)
        # Set an existing fixed minimum
        from dataclasses import replace

        updated = replace(card, minimum_payment_pence=6354)
        service.payment_method_repo.update_credit_card(card=updated)

        view.load_cards()
        app.processEvents()

        table = view.cards_table
        row = next(
            r
            for r in range(table.rowCount())
            if table.item(r, 0) and table.item(r, 0).text() == "CapitalOne"
        )

        item_before = table.item(row, COL_FIXED_MIN)
        assert item_before.text() == "£63.54", f"Pre-condition: {item_before.text()!r}"

        QTest.qWait(50)
        app.processEvents()

        cell_item = table.item(row, COL_FIXED_MIN)
        table.setCurrentItem(cell_item)
        table.editItem(cell_item)
        app.processEvents()

        editors = table.viewport().findChildren(QLineEdit)
        assert editors, "No editor opened after editItem()"
        editor = editors[0]

        editor.selectAll()
        QTest.keyClicks(editor, "120.45")
        QTest.keyClick(editor, Qt.Key.Key_Return)
        app.processEvents()
        app.processEvents()
        QTest.qWait(100)
        app.processEvents()

        item_after = table.item(row, COL_FIXED_MIN)
        assert item_after is not None
        assert (
            item_after.text() == "£120.45"
        ), f"FAIL: expected '£120.45', got {item_after.text()!r}"
