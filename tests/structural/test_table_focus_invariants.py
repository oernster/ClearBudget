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
import re
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


_QSS_SOURCES = (_UI,)

# Every item-view class. None of them may be given a border on hover or on
# focus: the current row is the indicator; a rectangle round the whole
# pane says something about a region the pointer sits inside rather than
# about anything the user is acting on.
_ITEM_VIEW_SELECTORS = frozenset(
    {
        "QAbstractItemView",
        "QListView",
        "QListWidget",
        "QTableView",
        "QTableWidget",
        "QTreeView",
        "QTreeWidget",
    }
)

_RING_PROPERTIES = ("border", "outline")
_INVISIBLE = ("none", "0", "0px", "transparent", "initial", "unset")

_BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
_DECLARATION = re.compile(r"([a-z-]+)\s*:\s*([^;]+)")


def _plain_qss(text: str) -> str:
    """Turn an f-string stylesheet into plain QSS without moving an offset.

    Every substitution keeps its original length, so a match offset still
    maps to the right source line. A stylesheet string either doubles its
    braces throughout or uses none, so one test settles which.
    """
    if "{{" not in text:
        return text
    marked = text.replace("{{", "{\x00").replace("}}", "}\x00")
    marked = re.sub(r"\{(?![\x00])[^{}]*\}", lambda m: "V" * len(m.group(0)), marked)
    return marked.replace("\x00", " ")


def _paints_a_ring(body: str) -> bool:
    for prop, value in _DECLARATION.findall(body):
        if not prop.startswith(_RING_PROPERTIES):
            continue
        cleaned = value.strip().strip(";").lower()
        if cleaned and not any(cleaned.startswith(dead) for dead in _INVISIBLE):
            return True
    return False


def item_view_ring_offences(text: str, where: str) -> list[str]:
    """Every rule giving an item view a visible border on hover or focus."""
    offences: list[str] = []
    plain = _plain_qss(text)
    for match in _BLOCK.finditer(plain):
        if not _paints_a_ring(match.group(2)):
            continue
        line = plain.count("\n", 0, match.start(2)) + 1
        for raw in match.group(1).split(","):
            part = " ".join(raw.strip().splitlines()[-1].split()) if raw.strip() else ""
            if ":hover" not in part and ":focus" not in part:
                continue
            for token in re.split(r"[\s>]+", part):
                token = token.strip()
                if "::" in token:
                    # A subcontrol is a control drawn inside the view, not the
                    # view itself, so it is styled like any other control.
                    continue
                if re.split(r"[:#\[]", token)[0] in _ITEM_VIEW_SELECTORS:
                    offences.append(f"{where}:{line}: {part}")
    return offences


class TestNoTableDrawsARingRoundItself:
    """The ring belongs to controls; a table shows the keyboard by its row."""

    def test_no_item_view_is_given_a_ring_in_any_state(self):
        offenders = []
        for root in _QSS_SOURCES:
            for path in sorted(root.rglob("*.py")):
                offenders.extend(
                    item_view_ring_offences(
                        path.read_text(encoding="utf-8"), str(path.relative_to(_ROOT))
                    )
                )

        assert not offenders, (
            "These rules outline a whole table. Its current row already shows "
            "where the keyboard is, so delete the rule and leave the "
            "transparent border in place:\n" + "\n".join(offenders)
        )

    def test_the_scan_reports_a_planted_ring(self):
        """A guard nobody has seen fail is not yet a guard."""
        hovered = (
            'S = f"""\nQTableWidget:enabled:hover {{ border: 2px solid {r}; }}\n"""'
        )
        focused = (
            'S = f"""\nQTableWidget:enabled:focus {{ border: 2px solid {r}; }}\n"""'
        )
        assert item_view_ring_offences(hovered, "planted")
        assert item_view_ring_offences(focused, "planted")

    def test_the_scan_leaves_controls_and_subcontrols_alone(self):
        """A button's ring and a table's own items are not the pane."""
        button = 'S = f"""\nQPushButton:enabled:focus {{ border: 2px solid {r}; }}\n"""'
        item = 'S = f"""\nQTableWidget::item:selected {{ border: 1px solid {r}; }}\n"""'
        assert not item_view_ring_offences(button, "button")
        assert not item_view_ring_offences(item, "item")
