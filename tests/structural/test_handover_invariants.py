"""The sign-in screen is never left stranded on screen.

Between `begin_handover` and `end_handover` the sign-in screen is visible and
INERT: an application-level filter swallows every mouse and key event aimed at
it, so it cannot be closed, moved through or typed into. That is right for the
two seconds it takes to build a window and it is unrecoverable for anything
longer, because the only thing that lifts the filter is `end_handover`.

Which makes the failure mode plain: any path out of the composition root's
session that skips `end_handover` leaves the user with a dead screen and no
window behind it, the process still running. A `finally` is the whole
guard; this test is what keeps the `finally` there.

Asserted by AST rather than by running the loop, because the suite is
deliberately Qt-free (see tests/conftest.py) and the loop it lives in owns the
event loop. The behaviour itself is verified by an offscreen probe.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_COMPOSITION_ROOT = _ROOT / "main.py"
_MIXIN = _ROOT / "clear_budget" / "ui" / "widgets" / "_handover_progress.py"

_BEGIN = "begin_handover"
_END = "end_handover"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _calls_named(node: ast.AST, name: str) -> list[ast.Call]:
    """Every `<anything>.name(...)` call anywhere under `node`."""
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == name
    ]


class TestTheHandoverAlwaysEnds:
    """Beginning a handover commits the code to ending it."""

    def test_every_begin_is_guarded_by_a_finally_that_ends_it(self):
        tree = _tree(_COMPOSITION_ROOT)
        begins = _calls_named(tree, _BEGIN)
        assert begins, f"main.py never calls {_BEGIN}; the guard has lost its subject"

        # A `Try` guards a begin when the begin is in its body and its
        # `finally` ends the handover. Matched on the call rather than on a
        # line number, so reformatting cannot retire the guard.
        guarded: set[int] = set()
        for try_node in [n for n in ast.walk(tree) if isinstance(n, ast.Try)]:
            if not any(
                _calls_named(stmt, _END) for stmt in try_node.finalbody
            ):  # pragma: no cover - a Try with no ending finally guards nothing
                continue
            for stmt in try_node.body:
                for call in _calls_named(stmt, _BEGIN):
                    guarded.add(id(call))

        stranded = [call for call in begins if id(call) not in guarded]
        assert not stranded, (
            f"main.py calls {_BEGIN} on line(s) "
            f"{sorted(call.lineno for call in stranded)} outside a try whose "
            f"finally calls {_END}. Raising from in there leaves the sign-in "
            "screen up, inert and unclosable, with no window behind it."
        )

    def test_ending_twice_is_safe(self):
        """The finally is a backstop, so it lands on top of the normal call."""
        source = _MIXIN.read_text(encoding="utf-8")
        tree = ast.parse(source)
        end = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == _END
        )
        first = end.body[1] if isinstance(end.body[0], ast.Expr) else end.body[0]
        assert isinstance(first, ast.If) and any(
            isinstance(stmt, ast.Return) for stmt in first.body
        ), (
            f"{_END} no longer returns early when there is nothing left to "
            "end, so the backstop in main.py would raise from a finally on "
            "a widget Qt has already destroyed."
        )
