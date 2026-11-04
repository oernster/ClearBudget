"""A bill's amount schedule is written by the view model, never by a view.

The view model refreshes the month summary after every write it makes; the
table is drawn from that summary. A view that writes the schedule to the
service directly writes it AFTER that refresh, so the table shows the amount
from before the change until something else happens to refresh it. That is
how a change effective from the current month was saved and not shown
(2026-11-04).

So the invariant is ownership: `set_bill_amount_changes` is called from the
view model package only. Asserted by source scan because the suite starts no
QApplication (see tests/conftest.py).
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_UI = _ROOT / "clear_budget" / "ui"
_VIEW_MODELS = _UI / "view_models"
_SERVICE_WRITE = "set_bill_amount_changes"


def _calls(source: str, name: str) -> int:
    return sum(
        1
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
    )


def _ui_modules_outside_the_view_models() -> list[Path]:
    return [
        path
        for path in _UI.rglob("*.py")
        if _VIEW_MODELS not in path.parents and "__pycache__" not in path.parts
    ]


def test_no_view_writes_the_amount_schedule_itself():
    offenders = [
        path.relative_to(_ROOT).as_posix()
        for path in _ui_modules_outside_the_view_models()
        if _calls(path.read_text(encoding="utf-8"), _SERVICE_WRITE)
    ]
    assert not offenders, (
        f"{_SERVICE_WRITE} must go through the view model, which refreshes the"
        f" summary after it; a view calling it writes after the refresh and the"
        f" table goes stale. Found in: {offenders}"
    )


def test_the_view_model_is_where_it_is_written():
    """The guard above is only meaningful while the write still exists."""
    total = sum(
        _calls(path.read_text(encoding="utf-8"), _SERVICE_WRITE)
        for path in _VIEW_MODELS.glob("*.py")
    )
    assert total >= 1
