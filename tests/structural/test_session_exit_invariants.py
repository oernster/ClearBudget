"""Switching user and signing out must stay two different things.

There are two ways out of a session and the ONLY difference between them is
what a cancelled sign-in then does. Switch User suspends: the window is hidden
and its database stays open, so cancelling returns to it. Log Out ends the
session: the composition root destroys the window and closes the database, so
cancelling closes the application.

That difference lives entirely in the wiring, which is why it is pinned here.
Cross the two signals and both menu items still work, both still land on the
sign-in screen and nothing raises; the only symptom is a cancelled Switch User
quietly closing the application, which is the exact bug this pair was built to
fix. Collapse them into one signal and the symptom is the same.

Asserted by source scan because the suite is deliberately Qt-free (see
tests/conftest.py); the behaviour itself is verified by an offscreen probe.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_WINDOW = _ROOT / "clear_budget" / "ui" / "main_window.py"
_ACCOUNT_MIXIN = _ROOT / "clear_budget" / "ui" / "_main_window_account.py"
_COMPOSITION_ROOT = _ROOT / "main.py"

_SWITCH_SIGNAL = "switch_user_requested"
_SIGN_OUT_SIGNAL = "sign_out_requested"
_SWITCH_HANDLER = "_on_switch_user"
_SIGN_OUT_HANDLER = "_on_sign_out"

# What signing out does that switching must not: forget the live window, so
# the cancel that follows has nothing to return to.
_DROP_WINDOW = "_drop_window"
# What the cancel path consults before it is allowed to quit.
_LIVE_WINDOW = "_active_window"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _class_level_names(tree: ast.Module, class_name: str) -> set[str]:
    """Every name assigned directly in `class_name`'s body."""
    node = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.ClassDef) and n.name == class_name
    )
    return {
        target.id
        for statement in node.body
        if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name)
    }


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    return next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name
    )


def _names_used_in(tree: ast.Module, function_name: str) -> set[str]:
    """Every identifier mentioned anywhere inside `function_name`."""
    used: set[str] = set()
    for node in ast.walk(_function(tree, function_name)):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
    return used


def _connections(tree: ast.Module) -> dict[str, set[str]]:
    """Map each `<something>.<signal>.connect(handler)` to its handler names."""
    wiring: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "connect"):
            continue
        if not isinstance(func.value, ast.Attribute):
            continue
        signal = func.value.attr
        for arg in node.args:
            if isinstance(arg, ast.Name):
                wiring.setdefault(signal, set()).add(arg.id)
            elif isinstance(arg, ast.Attribute):
                wiring.setdefault(signal, set()).add(arg.attr)
    return wiring


def test_the_window_declares_both_ways_out() -> None:
    """One signal for suspending the session, a different one for ending it."""
    signals = _class_level_names(_tree(_WINDOW), "MainWindow")
    for name in (_SWITCH_SIGNAL, _SIGN_OUT_SIGNAL):
        assert name in signals, (
            f"MainWindow no longer declares {name}, so the two ways out of a "
            "session cannot be told apart by the composition root"
        )


def test_each_handler_emits_its_own_signal() -> None:
    """Crossed wiring is silent, so it is asserted rather than trusted."""
    tree = _tree(_ACCOUNT_MIXIN)
    switch_emits = _names_used_in(tree, _SWITCH_HANDLER)
    sign_out_emits = _names_used_in(tree, _SIGN_OUT_HANDLER)
    assert _SWITCH_SIGNAL in switch_emits and _SIGN_OUT_SIGNAL not in switch_emits, (
        f"{_SWITCH_HANDLER} does not emit {_SWITCH_SIGNAL} alone; a switch "
        "that emits the sign-out signal ends the session it was suspending"
    )
    assert (
        _SIGN_OUT_SIGNAL in sign_out_emits and _SWITCH_SIGNAL not in sign_out_emits
    ), (
        f"{_SIGN_OUT_HANDLER} does not emit {_SIGN_OUT_SIGNAL} alone; a sign "
        "out that emits the switch signal leaves the session running"
    )


def test_the_two_signals_reach_different_handlers() -> None:
    """Wired to the same handler, the distinction stops existing."""
    wiring = _connections(_tree(_COMPOSITION_ROOT))
    switch_handlers = wiring.get(_SWITCH_SIGNAL, set())
    sign_out_handlers = wiring.get(_SIGN_OUT_SIGNAL, set())
    assert switch_handlers, f"{_SWITCH_SIGNAL} is never connected in main.py"
    assert sign_out_handlers, f"{_SIGN_OUT_SIGNAL} is never connected in main.py"
    assert not switch_handlers & sign_out_handlers, (
        "switching and signing out are wired to the same handler, so one of "
        "them is not doing what its menu item says"
    )


def test_only_the_sign_out_handler_forgets_the_live_window() -> None:
    """Suspending must KEEP the window; that is the whole of the difference."""
    tree = _tree(_COMPOSITION_ROOT)
    wiring = _connections(tree)
    (sign_out_handler,) = wiring[_SIGN_OUT_SIGNAL]
    assert _DROP_WINDOW in _names_used_in(tree, sign_out_handler), (
        f"{sign_out_handler} never calls {_DROP_WINDOW}, so signing out "
        "leaves a live window and a cancelled sign-in returns to a session "
        "the user asked to end"
    )


def _branch_tests_of(tree: ast.Module, function_name: str) -> list[set[str]]:
    """The identifiers each `if` inside `function_name` actually BRANCHES on."""
    tests: list[set[str]] = []
    for node in ast.walk(_function(tree, function_name)):
        if not isinstance(node, ast.If):
            continue
        names: set[str] = set()
        for inner in ast.walk(node.test):
            if isinstance(inner, ast.Name):
                names.add(inner.id)
            elif isinstance(inner, ast.Attribute):
                names.add(inner.attr)
        tests.append(names)
    return tests


def test_the_cancel_path_consults_the_live_window_before_quitting() -> None:
    """An unguarded quit here is the original bug, restored.

    The branch TEST is what is asserted, not merely that the name appears in
    the function. A first attempt checked only for the mention and a planted
    `if False:` walked straight through it, because the name still appeared
    inside the branch body it had just disabled.
    """
    tree = _tree(_COMPOSITION_ROOT)
    branch_tests = _branch_tests_of(tree, "_session_loop")
    assert any(_LIVE_WINDOW in names for names in branch_tests), (
        f"no branch in _session_loop tests {_LIVE_WINDOW}, so a cancelled "
        "sign-in quits the application even with a session still open"
    )
    assert "quit" in _names_used_in(tree, "_session_loop"), (
        "_session_loop never quits, so a cancelled sign-in with no session "
        "running leaves the application with no window and no way out"
    )
