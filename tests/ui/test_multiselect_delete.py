"""Tests for multi-select bill and income deletion (Ctrl and Shift selection patterns)."""

import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QItemSelectionModel

from clear_budget.domain.entities.bill import Bill
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

BILL_NAMES = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]
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


def _add_bills(service, names):
    """Insert bills and return list of saved Bill objects."""
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
    """Return names of currently active bills."""
    bills = service.bill_repo.list_active_for_month(year_month=MONTH)
    return {b.name for b in bills}


def _select_rows(view, rows):
    """Programmatically select specific rows in the bills table (simulates Ctrl+click)."""
    sel = view.bills_table.selectionModel()
    sel.clearSelection()
    for row in rows:
        for col in range(view.bills_table.columnCount()):
            idx = view.bills_table.model().index(row, col)
            sel.select(idx, QItemSelectionModel.SelectionFlag.Select)


def _select_range(view, first_row, last_row):
    """Programmatically select a contiguous range (simulates Shift+click)."""
    sel = view.bills_table.selectionModel()
    sel.clearSelection()
    for row in range(first_row, last_row + 1):
        for col in range(view.bills_table.columnCount()):
            idx = view.bills_table.model().index(row, col)
            sel.select(idx, QItemSelectionModel.SelectionFlag.Select)


# ---------------------------------------------------------------------------
# ViewModel layer — delete_bills batch logic
# ---------------------------------------------------------------------------

def test_delete_bills_all_ids_removed_from_db(app, service):
    """delete_bills removes every specified bill from the database."""
    saved = _add_bills(service, BILL_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)

    ids_to_delete = [saved[0].id, saved[2].id, saved[4].id]  # Alpha, Charlie, Echo
    vm.delete_bills(bill_ids=ids_to_delete)

    remaining = _active_bill_names(service)
    assert "Alpha" not in remaining,   "Alpha should be deleted"
    assert "Charlie" not in remaining, "Charlie should be deleted"
    assert "Echo" not in remaining,    "Echo should be deleted"
    assert "Bravo" in remaining,       "Bravo should survive"
    assert "Delta" in remaining,       "Delta should survive"


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
# UI layer — on_delete_bill with simulated selections
# ---------------------------------------------------------------------------

def test_ctrl_style_nonsequential_selection_deletes_all(app, service):
    """Ctrl+click non-sequential rows: Delete removes all selected bills."""
    _add_bills(service, BILL_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    # Bills are sorted by due day (col 4) by default; Alpha=day1, Bravo=day2 ... Echo=day5
    # Select rows 0, 2, 4 (Alpha, Charlie, Echo) — non-sequential, Ctrl-style
    _select_rows(view, [0, 2, 4])

    assert view.bills_table.selectedIndexes(), "Rows must be selected before delete"

    view.on_delete_bill()

    remaining = _active_bill_names(service)
    assert "Alpha" not in remaining,   "Row 0 (Alpha) must be deleted"
    assert "Charlie" not in remaining, "Row 2 (Charlie) must be deleted"
    assert "Echo" not in remaining,    "Row 4 (Echo) must be deleted"
    assert "Bravo" in remaining,       "Row 1 (Bravo) must survive"
    assert "Delta" in remaining,       "Row 3 (Delta) must survive"


def test_shift_style_sequential_range_deletes_all(app, service):
    """Shift+click contiguous range: Delete removes every bill in range."""
    _add_bills(service, BILL_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    # Select rows 1–3 (Bravo, Charlie, Delta) — contiguous, Shift-style
    _select_range(view, 1, 3)

    assert view.bills_table.selectedIndexes(), "Rows must be selected before delete"

    view.on_delete_bill()

    remaining = _active_bill_names(service)
    assert "Bravo" not in remaining,   "Row 1 (Bravo) must be deleted"
    assert "Charlie" not in remaining, "Row 2 (Charlie) must be deleted"
    assert "Delta" not in remaining,   "Row 3 (Delta) must be deleted"
    assert "Alpha" in remaining,       "Row 0 (Alpha) must survive"
    assert "Echo" in remaining,        "Row 4 (Echo) must survive"


def test_shift_style_full_range_deletes_all(app, service):
    """Shift+click selecting all rows deletes every bill."""
    _add_bills(service, BILL_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    _select_range(view, 0, 4)
    view.on_delete_bill()

    assert _active_bill_names(service) == set(), "All bills must be deleted"


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

    _select_rows(view, [0])  # Target is row 0 (sorted by day, day=1)
    view.on_delete_bill()

    remaining = _active_bill_names(service)
    assert "Target" not in remaining
    assert "Bystander" in remaining


def test_duplicate_names_ctrl_select_deletes_correct_bills(app, service):
    """Ctrl+click rows 0 and 2 with three identically-named bills deletes exactly those two.

    This is the real-world failure: 3x 'Amazon Prime' — selecting first and third
    must delete two distinct bills, not the same bill twice.
    """
    # Add 3 bills with identical names, different IDs (autoincrement)
    for i in range(3):
        service.bill_repo.add(bill=Bill(
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
        ))

    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    assert view.bills_table.rowCount() == 3, "Must have 3 rows before delete"

    # Select rows 0 and 2 (first and third Amazon Prime)
    _select_rows(view, [0, 2])
    view.on_delete_bill()

    all_bills = service.bill_repo.list_active_for_month(
        year_month=MONTH, include_inactive=True
    )
    assert len(all_bills) == 1, (
        f"Expected 1 bill remaining after deleting 2 of 3, got {len(all_bills)}"
    )


# ---------------------------------------------------------------------------
# Income helpers
# ---------------------------------------------------------------------------

def _add_incomes(service, names):
    """Insert income sources and return list of saved IncomeSource objects."""
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
    """Return names of all income sources still in the database (active only)."""
    return {i.name for i in service.income_repo.list_active()}


def _all_income_names(service):
    """Return names of all income sources (active + inactive) still in the database."""
    return {i.name for i in service.income_repo.list_all()}


def _select_income_rows(view, rows):
    """Programmatically select specific rows in the income table (simulates Ctrl+click)."""
    sel = view.income_table.selectionModel()
    sel.clearSelection()
    for row in rows:
        for col in range(view.income_table.columnCount()):
            idx = view.income_table.model().index(row, col)
            sel.select(idx, QItemSelectionModel.SelectionFlag.Select)


def _select_income_range(view, first_row, last_row):
    """Programmatically select a contiguous range (simulates Shift+click)."""
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

    ids_to_delete = [saved[0].id, saved[2].id, saved[4].id]  # Alpha, Charlie, Echo
    vm.delete_incomes(income_ids=ids_to_delete)

    remaining = _all_income_names(service)
    assert "Alpha" not in remaining,   "Alpha should be deleted"
    assert "Charlie" not in remaining, "Charlie should be deleted"
    assert "Echo" not in remaining,    "Echo should be deleted"
    assert "Bravo" in remaining,       "Bravo should survive"
    assert "Delta" in remaining,       "Delta should survive"


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

    # Income sorted by Name ascending by default: Alpha=0, Bravo=1, Charlie=2, Delta=3, Echo=4
    _select_income_rows(view, [0, 2, 4])

    assert view.income_table.selectedIndexes(), "Rows must be selected before delete"

    view.on_delete_income()

    remaining = _all_income_names(service)
    assert "Alpha" not in remaining,   "Row 0 (Alpha) must be deleted"
    assert "Charlie" not in remaining, "Row 2 (Charlie) must be deleted"
    assert "Echo" not in remaining,    "Row 4 (Echo) must be deleted"
    assert "Bravo" in remaining,       "Row 1 (Bravo) must survive"
    assert "Delta" in remaining,       "Row 3 (Delta) must survive"


def test_income_shift_style_sequential_range_deletes_all(app, service):
    """Shift+click contiguous income range: Delete removes every income in range."""
    _add_incomes(service, INCOME_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    # Select rows 1–3 (Bravo, Charlie, Delta)
    _select_income_range(view, 1, 3)

    assert view.income_table.selectedIndexes(), "Rows must be selected before delete"

    view.on_delete_income()

    remaining = _all_income_names(service)
    assert "Bravo" not in remaining,   "Row 1 (Bravo) must be deleted"
    assert "Charlie" not in remaining, "Row 2 (Charlie) must be deleted"
    assert "Delta" not in remaining,   "Row 3 (Delta) must be deleted"
    assert "Alpha" in remaining,       "Row 0 (Alpha) must survive"
    assert "Echo" in remaining,        "Row 4 (Echo) must survive"


def test_income_shift_style_full_range_deletes_all(app, service):
    """Shift+click selecting all income rows deletes every income."""
    _add_incomes(service, INCOME_NAMES)
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    _select_income_range(view, 0, 4)
    view.on_delete_income()

    assert _all_income_names(service) == set(), "All incomes must be deleted"


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

    # Sorted by name: Bystander=row0, Target=row1
    _select_income_rows(view, [1])
    view.on_delete_income()

    remaining = _all_income_names(service)
    assert "Target" not in remaining
    assert "Bystander" in remaining


def test_income_delete_removes_from_table_not_just_deactivates(app, service):
    """Delete Income hard-deletes: income must not appear in list_all() after deletion.

    Regression guard: previously delete_income called deactivate() which left
    the income in the database with active=False. The income stayed visible in
    the table (all_income_sources uses list_all). This test proves hard_delete
    is used instead.
    """
    saved = _add_incomes(service, ["Salary"])
    vm = MonthViewModel(budget_service=service, current_month=MONTH)
    view = MonthView(vm)

    assert view.income_table.rowCount() == 1, "Must have 1 row before delete"

    _select_income_rows(view, [0])
    view.on_delete_income()

    # Must not appear in list_all (not just list_active)
    all_incomes = service.income_repo.list_all()
    assert not any(i.id == saved[0].id for i in all_incomes), (
        "Deleted income must be removed from DB entirely, not just deactivated"
    )
    assert view.income_table.rowCount() == 0, "Table must be empty after delete"


def test_duplicate_income_names_ctrl_select_deletes_correct_incomes(app, service):
    """Ctrl+click rows 0 and 2 with three identically-named incomes deletes exactly those two.

    Real-world failure: 3x 'Salary' — selecting first and third must delete two
    distinct incomes, not the same income twice.
    """
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

    assert view.income_table.rowCount() == 3, "Must have 3 rows before delete"

    _select_income_rows(view, [0, 2])
    view.on_delete_income()

    all_incomes = service.income_repo.list_all()
    assert len(all_incomes) == 1, (
        f"Expected 1 income remaining after deleting 2 of 3, got {len(all_incomes)}"
    )
