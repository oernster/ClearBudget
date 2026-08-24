"""Save and Load must default to the app's data directory, not Downloads.

The difference is invisible when it regresses. Swap one helper for the other
and the dialog still opens, still works and still saves; it simply offers the
wrong folder, with nothing anywhere reporting it. So the choice is pinned rather
than left to whoever edits the flow next.

Downloads remains right for the exports that LEAVE the machine (the viewer
package, the graph exports, the full-backup zip), which is why the ban is
scoped to this one module rather than applied across the UI.

Asserted by source scan because the suite is deliberately Qt-free (see
tests/conftest.py); the directory the flows actually hand Qt is verified by
an offscreen probe that intercepts QFileDialog.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_FLOW = _ROOT / "clear_budget" / "ui" / "widgets" / "_save_load_flow.py"

_WANTED = "default_data_dir"
_BANNED = "default_downloads_dir"


def _names_used(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            used.update(alias.name for alias in node.names)
    return used


def test_the_save_and_load_flows_default_to_the_data_directory() -> None:
    assert _WANTED in _names_used(_FLOW), (
        f"{_FLOW.name} no longer uses {_WANTED}(), so Save and Load no longer "
        "offer the folder the budgets actually live in"
    )


def test_the_save_and_load_flows_never_default_to_downloads() -> None:
    assert _BANNED not in _names_used(_FLOW), (
        f"{_FLOW.name} uses {_BANNED}() again. Downloads is for files leaving "
        "the machine; a budget saved here is loaded straight back in"
    )
