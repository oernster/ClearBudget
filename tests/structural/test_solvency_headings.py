"""A section heading must not name a facility the reader may not have.

An overdraft facility is optional in ClearBudget and defaults to none. With
none arranged, the bank page's first section is not reporting on one at all:
it is saying whether the balance stays above zero, measured against a floor
of zero. Heading it "Overdraft Status" therefore named a facility the reader
had never set up and made a healthy account look as though it were being
measured against borrowing.

The invariant is the PRINCIPLE, not the replacement wording, so this scans
for the word rather than pinning the exact copy: a heading on the solvency
pages may not name the overdraft. The banner BODY may and does, because in a
critical state "NO OVERDRAFT FACILITY" is the fact that a payment will bounce
rather than draw on something arranged. That is a statement about what has
happened to the balance, not a label on a section the reader is browsing.

Asserted by source scan because the suite is deliberately Qt-free (see
tests/conftest.py). The rendered heading is verified by an offscreen probe.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_VIEWS = _ROOT / "clear_budget" / "ui" / "views"
_HEADING_BUILDER = "_heading"
_FORBIDDEN = "overdraft"

_PAGES = tuple(sorted(_VIEWS.glob("_solvency_panel_*.py")))


def _heading_literals(path: Path) -> list[str]:
    """Every string literal passed directly to `_heading(...)` in `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == _HEADING_BUILDER):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.append(arg.value)
    return found


def test_the_solvency_pages_have_headings_to_check() -> None:
    """Guard the guard: a scan that finds nothing proves nothing."""
    assert _PAGES, "no _solvency_panel_*.py modules were found to scan"
    total = sum(len(_heading_literals(p)) for p in _PAGES)
    assert total >= 4, (
        f"only {total} heading literals found across {len(_PAGES)} modules, so "
        "the scan is looking in the wrong place or _heading was renamed"
    )


def test_no_solvency_heading_names_the_overdraft() -> None:
    """No section heading may name an optional facility as though it were set."""
    for path in _PAGES:
        for text in _heading_literals(path):
            assert _FORBIDDEN not in text.casefold(), (
                f"{path.name} heads a section {text!r}, which names a facility "
                "that defaults to none; head it with what the section answers"
            )
