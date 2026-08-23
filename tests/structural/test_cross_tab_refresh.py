"""A tab must be refreshed by the data it displays, not by the tab it lives on.

The Credit Cards tab shows figures derived from the month's BILLS: a card's
Payment Received, its closing balance and the whole six-month projection are
all driven by a `credit_payment` bill. Those bills are created and edited on
the Monthly Budget tab; nothing on the Credit Cards tab moves when that
happens.

That is how the tab came to show figures computed when the window was built. A
card paid off every month projected a balance climbing past its own limit;
Payment Received sat at zero next to the bill that was paying it. Neither
number was wrong when it was calculated; both were simply never calculated
again. The user's only route out was to switch month and back.

So the invariant is the WIRING: `month_summary_updated`, which already keeps
Solvency in step, must also reach the Credit Cards view. Asserted by source
scan because the suite is deliberately Qt-free (see tests/conftest.py); a
widget-level test would need a real window, which is exactly what was removed.
The behaviour itself is verified by an offscreen probe.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MAIN_WINDOW = _ROOT / "clear_budget" / "ui" / "main_window.py"
_CARD_VIEW = _ROOT / "clear_budget" / "ui" / "views" / "credit_card_view.py"

_SIGNAL = "month_summary_updated"
_SLOT = "on_month_summary_updated"


def _connect_targets(source: str, signal: str) -> list[str]:
    """Every attribute name passed to `<...>.<signal>.connect(...)`."""
    targets = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "connect"):
            continue
        owner = func.value
        if not (isinstance(owner, ast.Attribute) and owner.attr == signal):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Attribute):
                targets.append(arg.attr)
            elif isinstance(arg, ast.Name):
                targets.append(arg.id)
    return targets


def _method_names(source: str, class_name: str) -> set[str]:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return set()


def test_the_card_view_exposes_the_summary_slot():
    """Named rather than a lambda, so its lifetime is the widget's."""
    assert _SLOT in _method_names(
        _CARD_VIEW.read_text(encoding="utf-8"), "CreditCardView"
    )


def test_the_card_view_is_refreshed_when_the_months_data_changes():
    targets = _connect_targets(_MAIN_WINDOW.read_text(encoding="utf-8"), _SIGNAL)
    assert _SLOT in targets, (
        f"{_SIGNAL} must reach the Credit Cards view or its panels and "
        f"projection go stale whenever a bill changes. Connected: {targets}"
    )


def test_solvency_is_still_wired_to_the_same_signal():
    """The precedent this fix followed; losing it would be the same bug again."""
    targets = _connect_targets(_MAIN_WINDOW.read_text(encoding="utf-8"), _SIGNAL)
    assert "update_month_summary" in targets, targets


def test_set_month_does_not_also_reload_the_cards():
    """One reload per month change, not two.

    `MonthViewModel.set_month` emits `month_changed` and THEN refreshes the
    summary, so a reload inside the view's `set_month` would be the first of
    two for a single click of Next. The month is still set there, because
    `load_cards` reads it.
    """
    source = _CARD_VIEW.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == "set_month":
            called = {
                sub.func.attr
                for sub in ast.walk(node)
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
            }
            assert (
                "load_cards" not in called
            ), "set_month must not reload; month_summary_updated does it"
            return
    raise AssertionError("CreditCardView.set_month not found")
