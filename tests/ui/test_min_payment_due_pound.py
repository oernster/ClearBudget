"""Proof tests: Min Payment Due (col 14) in Credit Cards tab always shows £ prefix.

Root bug: PySide6 EditTrigger.DoubleClicked opens inline editors on ALL cells,
ignoring ItemIsEditable flag. Col 14 (non-editable) shows raw "120.45" without £.
Fix: _on_card_item_changed reverts non-editable items via load_cards().
"""

import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

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
COL_MIN_PAYMENT_DUE = 14


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
    return CreditCardView(budget_service=service, current_month=MONTH)


class TestMinPaymentDuePoundPrefix:

    def test_amount_str_always_produces_pound_prefix(self):
        """Foundation: Amount.__str__ always returns £X.XX — underpins all display."""
        for pence in [0, 100, 2500, 6354, 12045, 295444]:
            result = str(Amount(pence=pence))
            assert result.startswith(
                "£"
            ), f"Amount(pence={pence}).__str__() = {result!r}"

    def test_col14_shows_pound_prefix_after_load_cards(self, view, service):
        """After load_cards(), col 14 Min Payment Due starts with £."""
        _add_card(service)
        view.load_cards()
        item = view.cards_table.item(0, COL_MIN_PAYMENT_DUE)
        assert item is not None, "Col 14 item must exist"
        assert item.text().startswith("£"), f"Col 14 text = {item.text()!r}"

    def test_col14_pound_prefix_for_known_balance_and_apr(self, view, service):
        """£62.88 monthly interest on £2954.44 balance → min payment has £ prefix."""
        _add_card(service, balance_pence=295444, apr=25.54)
        view.load_cards()
        item = view.cards_table.item(0, COL_MIN_PAYMENT_DUE)
        text = item.text()
        assert text.startswith("£"), f"Expected £ prefix, got {text!r}"
        assert len(text) > 1, "Must be more than just '£'"

    def test_col14_not_in_editable_cols_set(self, view, service):
        """Col 14 is NOT in _EDITABLE_COLS — root cause of the bug documented here.
        Qt gives all QTableWidgetItems ItemIsEditable by default; the handler
        uses a column allowlist instead of the flag."""
        _add_card(service)
        view.load_cards()
        assert (
            COL_MIN_PAYMENT_DUE not in view._EDITABLE_COLS
        ), "Col 14 must be outside the editable column set so handler reverts it"

    def test_col14_pound_prefix_survives_handler_call(self, app, view, service):
        """Core fix: calling _on_card_item_changed with non-editable col 14 item
        fires load_cards() which restores the £ prefix."""
        _add_card(service, balance_pence=295444, apr=25.54)
        view.load_cards()

        item = view.cards_table.item(0, COL_MIN_PAYMENT_DUE)
        assert item.text().startswith("£"), "Pre-condition: must start with £"

        # Simulate PySide6 bug: editor commits raw number to col 14 item
        view._on_card_item_changed(item)  # handler schedules QTimer(0, load_cards)

        # Fire the pending QTimer.singleShot(0, ...) callbacks
        app.processEvents()
        app.processEvents()

        new_item = view.cards_table.item(0, COL_MIN_PAYMENT_DUE)
        assert new_item is not None
        assert new_item.text().startswith(
            "£"
        ), f"After handler+revert: col 14 = {new_item.text()!r}, must have £"

    def test_all_cards_col14_have_pound_prefix(self, view, service):
        """Every card row in the table shows £ prefix in Min Payment Due."""
        _add_card(service, name="CapitalOne", balance_pence=143272, apr=25.69)
        _add_card(service, name="Vanquis", balance_pence=50000, apr=34.90)
        _add_card(service, name="Jaja", balance_pence=295444, apr=25.54)
        view.load_cards()

        row_count = view.cards_table.rowCount()
        assert row_count == 3, f"Expected 3 rows, got {row_count}"
        for row in range(row_count):
            item = view.cards_table.item(row, COL_MIN_PAYMENT_DUE)
            assert item is not None, f"Row {row} col 14 is None"
            assert item.text().startswith(
                "£"
            ), f"Row {row} col 14 = {item.text()!r}, must start with £"

    def test_col14_pound_preserved_after_another_column_edited(
        self, app, view, service
    ):
        """Editing an editable column (col 5 due day) and rebuilding still shows £ on col 14."""
        _add_card(service, balance_pence=139523, apr=24.9)
        view.load_cards()

        # Simulate editing col 5 (Due Day) — a legitimate editable column
        due_item = view.cards_table.item(0, 5)
        assert due_item.flags() & Qt.ItemFlag.ItemIsEditable

        # Trigger handler as if user changed due day
        view._on_card_item_changed(due_item)
        app.processEvents()
        app.processEvents()

        col14 = view.cards_table.item(0, COL_MIN_PAYMENT_DUE)
        assert col14 is not None
        assert col14.text().startswith(
            "£"
        ), f"After col-5 edit rebuild, col 14 = {col14.text()!r}"
