"""Pytest configuration and shared fixtures.

The test suite is deliberately Qt-free: the fragile widget-level PySide6 tests
were removed, and the UI layer is excluded from the coverage gate (see
.coveragerc). UI-layer logic that is pure Python is tested without a
QApplication under tests/ui_logic.

Every test also runs against a THROWAWAY data directory. See `isolate_app_dir`.
"""

import pytest

from clear_budget.shared.config import APP_DIR_ENV_VAR


@pytest.fixture(autouse=True)
def isolate_app_dir(tmp_path, monkeypatch):
    """Point the app's data directory at a scratch dir for EVERY test.

    Autouse and unconditional, because the alternative is remembering. The real
    directory holds live user data: both databases, the logs and the saved
    theme. Anything that writes there from outside the app changes what the
    user sees at their next launch, and a settings write is silent, so the
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
