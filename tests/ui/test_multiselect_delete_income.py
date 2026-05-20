"""Tests for multi-select income deletion (Ctrl and Shift selection patterns)."""

import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QItemSelectionModel

from clear_budget.domain.entities.income_source import IncomeSource
from clear_budget.domain.value_objects.amount import Amount
from clear_budget.domain.value_objects.year_month import YearMonth
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.income_source_repository import SQLiteIncomeSourceRepository
from clear_budget.infrastructure.sqlite.payment_method_repository import SQLitePaymentMethodRepository
from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.ui.view_models.month_view_model import MonthViewModel
from clear_budget.ui.views.month_view import MonthView


MONTH = YearMonth(2026, 5)
INCOME_NAMES = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]


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


def _add_incomes(service, names):
    saved = []
    for i, name in enumerate(names):
        inc = IncomeSource(
            id=0,
            name=name,
            amount=Amount.from_pounds(100 + i * 50),
            is_reliable=True,
            day_of_month=i + 1,
            active=True,
        )
        saved.append(service.income_repo.add(income=inc))
    return saved


def _active_income_names(service):
    return {i.name for i in service.income_repo.list_active()}


def _all_income_names(service):
    return {i.name for i in service.income_repo.list_all()}


def _select_income_rows(view, rows):
    sel = view.income_table.selectionModel()
    sel.clearSelection()
    for row in rows:
        for col in range(view.income_table.columnCount()):
            idx = view.income_table.model().index(row, col)
            sel.select(idx, QItemSelectionModel.SelectionFlag.Select)


def _select_income_range(view, first_row, last_row):
    sel = view.income_table.selectionModel()
    sel.clearSelection()
    for row in range(first_row, last_row + 1):
        for col in range(view.income_table.columnCount()):
            idx = view.income_table.model().index(row, col)
            sel.select(idx, QItemSelectionModel.SelectionFlag.Select)


# ---------------------------------------------------------------------------
# ViewModel layer — delete_incomes batch logic
# ---------------------------------------------------------------------------

def test_delete_incomes_all_ids_removed_from_db(app, service):
    """delete_incomes removes every specified income from the database."""
    saved = _add_incomes(service, INCOME_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)

    ids_to_delete = [saved[0].id, saved[2].id, saved[4].id]
    vm.delete_incomes(income_ids=ids_to_delete)

    remaining = _all_income_names(service)
    assert "Alpha" not in remaining
    assert "Charlie" not in remaining
    assert "Echo" not in remaining
    assert "Bravo" in remaining
    assert "Delta" in remaining


def test_delete_incomes_single_id(app, service):
    """delete_incomes with one ID deletes exactly that income."""
    saved = _add_incomes(service, ["Only", "Other"])
    vm = MonthViewModel(budget_service=service, current_month=MONTH)

    vm.delete_incomes(income_ids=[saved[0].id])

    remaining = _all_income_names(service)
    assert "Only" not in remaining
    assert "Other" in remaining


def test_delete_incomes_all_incomes(app, service):
    """delete_incomes with every ID leaves no income sources."""
    saved = _add_incomes(service, ["X", "Y", "Z"])
    vm = MonthViewModel(budget_service=service, current_month=MONTH)

    vm.delete_incomes(income_ids=[i.id for i in saved])

    assert _all_income_names(service) == set()


# ---------------------------------------------------------------------------
# UI layer — on_delete_income with simulated selections
# ---------------------------------------------------------------------------

def test_income_ctrl_style_nonsequential_selection_deletes_all(app, service):
    """Ctrl+click non-sequential income rows: Delete removes all selected incomes."""
    _add_incomes(service, INCOME_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    _select_income_rows(view, [0, 2, 4])
    assert view.income_table.selectedIndexes()

    view.on_delete_income()

    remaining = _all_income_names(service)
    assert "Alpha" not in remaining
    assert "Charlie" not in remaining
    assert "Echo" not in remaining
    assert "Bravo" in remaining
    assert "Delta" in remaining


def test_income_shift_style_sequential_range_deletes_all(app, service):
    """Shift+click contiguous income range: Delete removes every income in range."""
    _add_incomes(service, INCOME_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    _select_income_range(view, 1, 3)
    assert view.income_table.selectedIndexes()

    view.on_delete_income()

    remaining = _all_income_names(service)
    assert "Bravo" not in remaining
    assert "Charlie" not in remaining
    assert "Delta" not in remaining
    assert "Alpha" in remaining
    assert "Echo" in remaining


def test_income_shift_style_full_range_deletes_all(app, service):
    """Shift+click selecting all income rows deletes every income."""
    _add_incomes(service, INCOME_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    _select_income_range(view, 0, 4)
    view.on_delete_income()

    assert _all_income_names(service) == set()


def test_no_income_selection_deletes_nothing(app, service):
    """Clicking Delete Income with nothing selected leaves all incomes intact."""
    _add_incomes(service, ["Safe1", "Safe2"])
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    view.income_table.clearSelection()
    view.on_delete_income()

    remaining = _all_income_names(service)
    assert "Safe1" in remaining
    assert "Safe2" in remaining


def test_income_ctrl_style_single_row_deletes_one(app, service):
    """Ctrl+click on a single income row deletes exactly that income."""
    _add_incomes(service, ["Target", "Bystander"])
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    _select_income_rows(view, [1])
    view.on_delete_income()

    remaining = _all_income_names(service)
    assert "Target" not in remaining
    assert "Bystander" in remaining


def test_income_delete_removes_from_table_not_just_deactivates(app, service):
    """Delete Income hard-deletes: income must not appear in list_all() after deletion."""
    saved = _add_incomes(service, ["Salary"])
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    assert view.income_table.rowCount() == 1

    _select_income_rows(view, [0])
    view.on_delete_income()

    all_incomes = service.income_repo.list_all()
    assert not any(i.id == saved[0].id for i in all_incomes), (
        "Deleted income must be removed from DB entirely, not just deactivated"
    )
    assert view.income_table.rowCount() == 0


def test_duplicate_income_names_ctrl_select_deletes_correct_incomes(app, service):
    """Ctrl+click rows 0 and 2 with three identically-named incomes deletes exactly those two."""
    for i in range(3):
        service.income_repo.add(income=IncomeSource(
            id=0,
            name="Salary",
            amount=Amount.from_pounds(1000 + i * 100),
            is_reliable=True,
            day_of_month=i + 1,
            active=True,
        ))

    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    assert view.income_table.rowCount() == 3

    _select_income_rows(view, [0, 2])
    view.on_delete_income()

    all_incomes = service.income_repo.list_all()
    assert len(all_incomes) == 1, f"Expected 1 remaining, got {len(all_incomes)}"
