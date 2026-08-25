"""The signed-in account must be shown, on every view.

Three pieces make it: the header builds the label AND its mirror, MainWindow
fills it in for every tray, the title bar no longer duplicates it. Each
one fails silently on its own. Drop the label and the tray simply has a gap;
drop the mirror and the month cluster stops being centred on the window,
drifting by half the name's width and by a different amount per account; drop
the fill and every tray shows an empty space where a name should be, which is
exactly what happened once already, because ScrollableView lifts the header out
of its view and the name was being set by searching the view.

Asserted by source scan because the suite is deliberately Qt-free (see
tests/conftest.py); the appearance is verified by rendering the real window.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_HEADER = _ROOT / "clear_budget" / "ui" / "utils" / "nav_header.py"
# The trays are filled in where the pages are built, which is here
# since main_window was split at the LOC danger band.
_WINDOW = _ROOT / "clear_budget" / "ui" / "_main_window_views.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _calls_in(tree: ast.Module, function_name: str) -> set[str]:
    """Every plain `name(...)` call made inside `function_name`."""
    target = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == function_name
    )
    return {
        node.func.id
        for node in ast.walk(target)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_month_tray_builds_the_label_and_its_mirror() -> None:
    """Without the mirror the month stops being centred on the window.

    The CALL is what is asserted, not the name appearing somewhere in the
    file. A first attempt looked for the text `_build_nav_user_pair()` and a
    planted violation walked straight through it, because removing the call
    leaves the definition behind, which contains the same text.
    """
    tree = ast.parse(_source(_HEADER))
    built = _calls_in(tree, "build_centered_nav_header")
    assert "_build_nav_user_pair" in built, (
        "the month tray no longer builds the account label, so nothing names "
        "the account whose budget is on screen"
    )
    mirrored = _calls_in(tree, "_build_nav_user_pair")
    assert "QWidget" in mirrored, (
        "the account label lost its mirror, so the month cluster is centred "
        "on what the name leaves behind rather than on the window"
    )


def test_a_long_account_name_is_shortened_rather_than_left_to_grow() -> None:
    """Unbounded, a long name pushes the month off the middle of the window."""
    label_module = _HEADER.parent / "nav_label.py"
    source = label_module.read_text(encoding="utf-8")
    # The CALL, not the constant: leaving the constant defined while dropping
    # the call is exactly what a careless edit does; a name-only check
    # cannot tell the two apart.
    methods = {
        node.func.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "setMaximumWidth" in methods, (
        "the account label has no maximum width, so a long name grows until "
        "it costs the month cluster its space"
    )
    assert "elidedText" in source, (
        "the account label no longer shortens a name that does not fit, so a "
        "long one is simply clipped"
    )
    assert "setToolTip" in source, (
        "a shortened name is no longer recoverable on hover, so part of the "
        "account name is simply gone"
    )


def test_the_window_fills_the_label_in_on_every_tray() -> None:
    """Every view builds its own tray, so every view needs the name set."""
    tree = ast.parse(_source(_WINDOW))
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "set_nav_user" in called, (
        "MainWindow never calls set_nav_user, so every tray shows an empty "
        "space where the account name belongs"
    )


def test_the_title_bar_no_longer_names_the_account() -> None:
    """It moved because it was unreadably small there; two copies drift."""
    tree = ast.parse(_source(_WINDOW))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "setWindowTitle":
            continue
        for arg in node.args:
            assert isinstance(arg, ast.Constant), (
                "the window title is built from something again; the account "
                "belongs in the month tray, where it can be read"
            )
