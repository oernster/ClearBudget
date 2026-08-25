"""The ring's entry point is a view decision and the wiring must hold.

Three pieces make the behaviour: a view declares `nav_entry_stop()` (the
control the first Tab lands on after arriving on that view), MainWindow hands
the navigator a callable that asks the active view and the navigator prefers
that stop when the ring is entered from neutral. Any of the three silently
missing degrades to "first Tab goes to the File menu", which reads as the
feature never existing rather than as a failure, so each is pinned here.

Asserted by source scan because the suite is deliberately Qt-free (see
tests/conftest.py); the behaviour itself (which control actually takes the
ring on the first press, the pilot handover on a page turn) is verified by
an offscreen probe.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_UI = _ROOT / "clear_budget" / "ui"
_NAV_MIXIN = _UI / "_main_window_nav.py"
_NAVIGATOR = _UI / "keyboard_nav.py"

# The views that declare an entry stop. Monthly Budget and Archive keep the
# default (menu-first) entry on purpose.
_ENTRY_VIEWS = (
    _UI / "views" / "solvency_panel.py",
    _UI / "views" / "credit_card_view.py",
)

_ENTRY_METHOD = "nav_entry_stop"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _methods(tree: ast.Module) -> set[str]:
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def test_the_entry_views_declare_their_entry_stop() -> None:
    for path in _ENTRY_VIEWS:
        assert _ENTRY_METHOD in _methods(_tree(path)), (
            f"{path.name} defines no {_ENTRY_METHOD}(), so the first Tab on "
            "that view falls back to the File menu"
        )


def test_the_main_window_hands_the_navigator_an_entry_callable() -> None:
    tree = _tree(_NAV_MIXIN)
    assert "_current_nav_entry" in _methods(tree), (
        f"{_NAV_MIXIN.name} defines no _current_nav_entry, so no view's "
        "entry stop can reach the navigator"
    )
    wired = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "entry_stop":
                    wired = True
    assert wired, (
        f"{_NAV_MIXIN.name} never passes entry_stop= to the navigator, so "
        "the declared entry stops are dead code"
    )
    entry_fn = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_current_nav_entry"
    )
    assert _ENTRY_METHOD in ast.dump(
        entry_fn
    ), f"_current_nav_entry never asks the view for {_ENTRY_METHOD}"


def test_the_navigator_prefers_the_entry_stop_from_neutral() -> None:
    tree = _tree(_NAVIGATOR)
    entry_methods = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "_entry"
    ]
    assert entry_methods, (
        f"{_NAVIGATOR.name} has no _entry(), so a neutral start always "
        "enters at the ring's first stop"
    )
    assert "_entry_stop" in ast.dump(entry_methods[0]), (
        "_entry() never consults self._entry_stop, so the view's declared "
        "entry point is ignored"
    )


def test_a_solvency_page_turn_hands_focus_to_the_revert_pilot() -> None:
    tree = _tree(_UI / "views" / "solvency_panel.py")
    show_page = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "_show_page"
        ),
        None,
    )
    assert show_page is not None, "solvency_panel.py lost _show_page"
    assert "setFocus" in ast.dump(show_page), (
        "_show_page never focuses the surviving pilot, so turning the page "
        "strands the keyboard where the pressed button was hidden"
    )
