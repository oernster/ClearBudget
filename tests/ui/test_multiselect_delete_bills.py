"""Tests for multi-select bill deletion (Ctrl and Shift selection patterns)."""

import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QItemSelectionModel

from clear_budget.domain.entities.bill import Bill
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

MONTH = YearMonth(2026, 5)
BILL_NAMES = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]


@pytest.fixture
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
    gen = MonthGenerator(bill_repo, income_repo)
    return BudgetService(
        bill_repo=bill_repo,
        income_repo=income_repo,
        payment_method_repo=pm_repo,
        month_generator=gen,
    )


def _add_bills(service, names):
    saved = []
    for i, name in enumerate(names):
        bill = Bill(
            id=0,
            name=name,
            amount=Amount.from_pounds(10 + i),
            payment_method_id=1,
            category="groceries",
            bill_type="fixed",
            day_of_month=i + 1,
            start_ym=MONTH,
            end_ym=None,
            active=True,
        )
        saved.append(service.bill_repo.add(bill=bill))
    return saved


def _active_bill_names(service):
    bills = service.bill_repo.list_active_for_month(year_month=MONTH)
    return {b.name for b in bills}


def _select_rows(view, rows):
    sel = view.bills_table.selectionModel()
    sel.clearSelection()
    for row in rows:
        for col in range(view.bills_table.columnCount()):
            idx = view.bills_table.model().index(row, col)
            sel.select(idx, QItemSelectionModel.SelectionFlag.Select)


def _select_range(view, first_row, last_row):
    sel = view.bills_table.selectionModel()
    sel.clearSelection()
    for row in range(first_row, last_row + 1):
        for col in range(view.bills_table.columnCount()):
            idx = view.bills_table.model().index(row, col)
            sel.select(idx, QItemSelectionModel.SelectionFlag.Select)


# ---------------------------------------------------------------------------
# ViewModel layer: delete_bills batch logic
# ---------------------------------------------------------------------------


def test_delete_bills_all_ids_removed_from_db(app, service):
    """delete_bills removes every specified bill from the database."""
    saved = _add_bills(service, BILL_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)

    ids_to_delete = [saved[0].id, saved[2].id, saved[4].id]
    vm.delete_bills(bill_ids=ids_to_delete)

    remaining = _active_bill_names(service)
    assert "Alpha" not in remaining
    assert "Charlie" not in remaining
    assert "Echo" not in remaining
    assert "Bravo" in remaining
    assert "Delta" in remaining


def test_delete_bills_single_id(app, service):
    """delete_bills with one ID deletes exactly that bill."""
    saved = _add_bills(service, ["Only", "Other"])
    vm = MonthViewModel(budget_service=service, current_month=MONTH)

    vm.delete_bills(bill_ids=[saved[0].id])

    remaining = _active_bill_names(service)
    assert "Only" not in remaining
    assert "Other" in remaining


def test_delete_bills_all_bills(app, service):
    """delete_bills with every ID leaves no active bills."""
    saved = _add_bills(service, ["X", "Y", "Z"])
    vm = MonthViewModel(budget_service=service, current_month=MONTH)

    vm.delete_bills(bill_ids=[b.id for b in saved])

    assert _active_bill_names(service) == set()


# ---------------------------------------------------------------------------
# UI layer: on_delete_bill with simulated selections
# ---------------------------------------------------------------------------


def test_ctrl_style_nonsequential_selection_deletes_all(app, service):
    """Ctrl+click non-sequential rows: Delete removes all selected bills."""
    _add_bills(service, BILL_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    _select_rows(view, [0, 2, 4])
    assert view.bills_table.selectedIndexes()

    view.on_delete_bill()

    remaining = _active_bill_names(service)
    assert "Alpha" not in remaining
    assert "Charlie" not in remaining
    assert "Echo" not in remaining
    assert "Bravo" in remaining
    assert "Delta" in remaining


def test_shift_style_sequential_range_deletes_all(app, service):
    """Shift+click contiguous range: Delete removes every bill in range."""
    _add_bills(service, BILL_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    _select_range(view, 1, 3)
    assert view.bills_table.selectedIndexes()

    view.on_delete_bill()

    remaining = _active_bill_names(service)
    assert "Bravo" not in remaining
    assert "Charlie" not in remaining
    assert "Delta" not in remaining
    assert "Alpha" in remaining
    assert "Echo" in remaining


def test_shift_style_full_range_deletes_all(app, service):
    """Shift+click selecting all rows deletes every bill."""
    _add_bills(service, BILL_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    _select_range(view, 0, 4)
    view.on_delete_bill()

    assert _active_bill_names(service) == set()


def test_no_selection_deletes_nothing(app, service):
    """Clicking Delete with nothing selected leaves all bills intact."""
    _add_bills(service, ["Safe1", "Safe2"])
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    view.bills_table.clearSelection()
    view.on_delete_bill()

    remaining = _active_bill_names(service)
    assert "Safe1" in remaining
    assert "Safe2" in remaining


def test_ctrl_style_single_row_deletes_one(app, service):
    """Ctrl+click on a single row deletes exactly that bill."""
    _add_bills(service, ["Target", "Bystander"])
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    _select_rows(view, [0])
    view.on_delete_bill()

    remaining = _active_bill_names(service)
    assert "Target" not in remaining
    assert "Bystander" in remaining


def test_duplicate_names_ctrl_select_deletes_correct_bills(app, service):
    """Ctrl+click rows 0 and 2 with three identically-named bills deletes exactly those two."""
    for i in range(3):
        service.bill_repo.add(
            bill=Bill(
                id=0,
                name="Amazon Prime",
                amount=Amount.from_pounds(8 + i),
                payment_method_id=1,
                category="subscriptions",
                bill_type="fixed",
                day_of_month=i + 1,
                start_ym=MONTH,
                end_ym=None,
                active=True,
            )
        )

    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    assert view.bills_table.rowCount() == 3

    _select_rows(view, [0, 2])
    view.on_delete_bill()

    all_bills = service.bill_repo.list_active_for_month(
        year_month=MONTH, include_inactive=True
    )
    assert len(all_bills) == 1, f"Expected 1 remaining, got {len(all_bills)}"


def test_delete_stop_from_viewed_month_preserves_earlier(app, service, monkeypatch):
    """'Stop from <month>' ends the bill at the prior month, keeping history."""
    monkeypatch.setattr(MonthView, "_ask_delete_scope", lambda self, *a, **k: "stop")
    saved = service.bill_repo.add(
        bill=Bill(
            id=0,
            name="Sub",
            amount=Amount.from_pounds(9),
            payment_method_id=1,
            category="subscriptions",
            bill_type="fixed",
            day_of_month=1,
            start_ym=YearMonth(2026, 1),
            end_ym=None,
            active=True,
        )
    )
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)
    _select_rows(view, [0])
    view.on_delete_bill()

    # MONTH is 2026-05; "stop" sets the end to the prior month (April 2026).
    bill = service.bill_repo.get_by_id(bill_id=saved.id)
    assert bill.end_ym == YearMonth(2026, 4)
    assert "Sub" not in _active_bill_names(service)  # gone from May onward
    april = service.bill_repo.list_active_for_month(year_month=YearMonth(2026, 4))
    assert "Sub" in {b.name for b in april}  # earlier months preserved
    jan = service.bill_repo.list_active_for_month(year_month=YearMonth(2026, 1))
    assert "Sub" in {b.name for b in jan}
