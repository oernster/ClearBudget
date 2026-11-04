"""Pytest configuration and shared fixtures.

The test suite deliberately starts no QApplication and has no widget tests:
the fragile widget-level PySide6 tests were removed; the UI layer is excluded
from the coverage gate (see .coveragerc). UI-layer logic that is pure Python
is tested without a QApplication under tests/ui_logic. PySide6 is still
imported: a few tests take Qt classes or enums directly; others import UI
modules that load it.

Every test also runs against a THROWAWAY data directory. See `isolate_app_dir`.
"""

import pytest

from clear_budget.application.services.budget_service import BudgetService
from clear_budget.application.services.month_generator import MonthGenerator
from clear_budget.infrastructure.sqlite.bill_repository import SQLiteBillRepository
from clear_budget.infrastructure.sqlite.database import Database
from clear_budget.infrastructure.sqlite.income_source_repository import (
    SQLiteIncomeSourceRepository,
)
from clear_budget.infrastructure.sqlite.payment_method_repository import (
    SQLitePaymentMethodRepository,
)
from clear_budget.shared.config import APP_DIR_ENV_VAR


@pytest.fixture(autouse=True)
def isolate_app_dir(tmp_path, monkeypatch):
    """Point the app's data directory at a scratch dir for EVERY test.

    Autouse and unconditional, because the alternative is remembering. The real
    directory holds live user data: both databases, the logs and the saved
    theme. Anything that writes there from outside the app changes what the
    user sees at their next launch; a settings write is silent, so the
    damage surfaces later as a bug report against the app itself.

    The scratch directory is NAMED `.clearbudget` like the real one, so tests
    asserting on the directory name still hold while its location cannot be the
    user's home. A test that needs the unredirected path clears the variable
    itself through `real_app_dir`, which is explicit and scoped to that test.
    """
    app_dir = tmp_path / ".clearbudget"
    monkeypatch.setenv(APP_DIR_ENV_VAR, str(app_dir))
    return app_dir


@pytest.fixture
def real_app_dir(monkeypatch):
    """Undo the redirect, for the few tests that assert the real path shape.

    Nothing under it is written: these tests only look at where the path lands.
    """
    monkeypatch.delenv(APP_DIR_ENV_VAR, raising=False)


@pytest.fixture()
def budget_service(tmp_path):
    """BudgetService wired to a temp SQLite database.

    Shared here rather than kept under tests/application, because the
    Qt-free view model tests under tests/ui_logic drive the same service.
    """
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
