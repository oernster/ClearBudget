"""No table takes the ring from a click.

A table's default focus policy is `StrongFocus`, which grants CLICK focus as
well, so clicking anywhere in one, including the empty space below the last row
where a click does nothing at all, put the ring around the whole pane. The ring
means the keyboard is here; a pane outlined by a pointer says something that is
not true; the next Tab resumes from a place the user never chose.

`keyboard_only_focus` (clear_budget/ui/utils/table_focus.py) sets `TabFocus` on
every one of them. Doing nothing is the WRONG state here, which is exactly why
this test exists: a table added later inherits the bad default silently, with
nothing about it looking wrong in review.

Source scan because the suite is deliberately Qt-free (see tests/conftest.py);
the behaviour on both policies was measured with an offscreen probe.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_UI = _ROOT / "clear_budget" / "ui"

_TABLE_TYPES = frozenset({"QTableWidget", "QTableView"})
_HELPER = "keyboard_only_focus"
# Where the helper lives; it is the one place allowed to name the policy.
_HELPER_MODULE = _UI / "utils" / "table_focus.py"


def _tables_built_in(tree: ast.Module) -> dict[str, int]:
    """Name each constructed table is bound to, to the line that built it."""
    built: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        callee = node.value.func
        name = (
            callee.id if isinstance(callee, ast.Name) else getattr(callee, "attr", "")
        )
        if name not in _TABLE_TYPES:
            continue
        for target in node.targets:
            built[ast.unparse(target)] = node.lineno
    return built


def _helper_arguments(tree: ast.Module) -> set[str]:
    return {
        ast.unparse(node.args[0])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _HELPER
        and node.args
    }


class TestEveryTableTakesFocusFromTheRingOnly:
    """Building a table commits the module to saying how focus reaches it."""

    def test_every_table_built_in_the_ui_gets_the_helper(self):
        offenders = []
        for path in sorted(_UI.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            treated = _helper_arguments(tree)
            for table, lineno in sorted(_tables_built_in(tree).items()):
                if table not in treated:
                    offenders.append(
                        f"{path.relative_to(_ROOT)}:{lineno}: {table} never "
                        f"reaches {_HELPER}"
                    )

        assert not offenders, (
            "These tables keep Qt's default StrongFocus, so clicking one, "
            "including the dead space below its last row, wraps the whole "
            f"pane in the ring. Call {_HELPER}(<table>) beside the other "
            "per-table setup.\n" + "\n".join(offenders)
        )

    def test_no_table_sets_its_own_focus_policy(self):
        """One place decides, so the answer cannot drift table by table."""
        offenders = []
        for path in sorted(_UI.rglob("*.py")):
            if path == _HELPER_MODULE:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            tables = set(_tables_built_in(tree))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                callee = node.func
                if (
                    isinstance(callee, ast.Attribute)
                    and callee.attr == "setFocusPolicy"
                    and ast.unparse(callee.value) in tables
                ):
                    offenders.append(
                        f"{path.relative_to(_ROOT)}:{node.lineno}: "
                        f"{ast.unparse(callee.value)} sets its own policy"
                    )

        assert not offenders, (
            f"A table's focus policy belongs in {_HELPER_MODULE.name}, where "
            "the reasoning lives, not at the table:\n" + "\n".join(offenders)
        )
