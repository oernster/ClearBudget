"""Every combo box in the application must be a ThemedComboBox.

The app-wide stylesheet makes `QComboBox::drop-down` invisible, which is what
rounds the control's right-hand corner; the same rule stops the platform
painting the chevron, so `ThemedComboBox` paints one itself. The two halves
only work together.

A plain `QComboBox` therefore still builds, still drops down and still works
by keyboard and mouse. It simply has no arrow, which reads as a text field
that mysteriously opens a list; nothing fails to announce it. That is what
these pin.

Asserted by source scan because the suite is deliberately Qt-free (see
tests/conftest.py); the appearance itself is verified by rendering the real
dialogs on the Windows platform.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_UI = _ROOT / "clear_budget" / "ui"
_THEME_INPUTS = _UI / "_theme_inputs.py"
_THEMED_COMBO = _UI / "widgets" / "themed_combo_box.py"

_PLAIN = "QComboBox"
_THEMED = "ThemedComboBox"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _constructed_names(path: Path) -> set[str]:
    """Every plain name called as `Name(...)` anywhere in `path`."""
    return {
        node.func.id
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _ui_modules() -> list[Path]:
    return [
        path
        for path in _UI.rglob("*.py")
        if "__pycache__" not in path.parts and path != _THEMED_COMBO
    ]


def test_no_ui_module_builds_a_plain_combo_box() -> None:
    """A plain one draws no arrow; nothing else says so."""
    offenders = [
        path.relative_to(_ROOT).as_posix()
        for path in _ui_modules()
        if _PLAIN in _constructed_names(path)
    ]
    assert not offenders, (
        "these build a plain QComboBox, which the app-wide stylesheet leaves "
        f"with no drop-down arrow; use {_THEMED} instead:\n  " + "\n  ".join(offenders)
    )


def test_the_themed_combo_box_still_paints_its_own_arrow() -> None:
    """Lose the paint handler and every dropdown loses its arrow at once."""
    tree = _tree(_THEMED_COMBO)
    combo = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == _THEMED
    )
    bases = {base.id for base in combo.bases if isinstance(base, ast.Name)}
    assert _PLAIN in bases, f"{_THEMED} no longer extends {_PLAIN}"
    methods = {n.name for n in combo.body if isinstance(n, ast.FunctionDef)}
    assert "paintEvent" in methods, (
        f"{_THEMED} defines no paintEvent, so nothing draws the arrow the "
        "stylesheet stopped the platform drawing"
    )


def test_the_stylesheet_still_hides_the_native_drop_down() -> None:
    """The other half: without this the corner goes square again."""
    sheet = _THEME_INPUTS.read_text(encoding="utf-8")
    assert "QComboBox::drop-down" in sheet, (
        f"{_THEME_INPUTS.name} no longer styles ::drop-down, so the native "
        "button paints over the rounded right-hand corner again"
    )
    rule = sheet[sheet.index("QComboBox::drop-down") :]
    rule = rule[: rule.index("}}")]
    assert "background: transparent" in rule, (
        "the ::drop-down rule no longer makes the subcontrol transparent, so "
        "the native button is back over the corner AND its arrow is drawn "
        "under the painted one"
    )
