"""A view takes the button run whole; Archive comes off the end. No more.

Every view builds its own copy of the strip as `self.tab_btns`, whose ring
declaration has to say which of those buttons are stops. Two slices are
legitimate and appear in every view: `[:-1]` is the run as drawn and `[-1:]`
is Archive, which sits in the right-hand group rather than in the run.

Scoped to `nav_targets`, which is where a ring is declared. The layout code
naming a single button (`pre_theme=(self.tab_btns[-1],)` puts Archive in the
right-hand group) is a different act and cannot drop a stop from a ring.

Any OTHER slice is how a view silently leaves the ring. Solvency needed its
page-turn pilots inside the run, so it cut the run up and reassembled it as
`[:2]`, `[2:3]` and `[-1:]`: five view buttons, four positions, no arithmetic anywhere
saying that the fifth had been dropped. The Graph button was absent from that
view's ring entirely, which presents as the ring jumping a button that is
plainly on screen.

The repair is `tab_icons.stops_before`, which inserts into the whole run
instead of slicing it. This asserts nobody goes back to slicing, since the
result of doing so is invisible in review and invisible in the tests: the
ring simply skips something.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_UI = _ROOT / "clear_budget" / "ui"

_RUN_ATTRIBUTE = "tab_btns"
_DECLARATION = "nav_targets"
# The run as drawn, plus Archive off the end.
_ALLOWED = frozenset({"self.tab_btns[:-1]", "self.tab_btns[-1:]"})


def _tab_run_slices(tree: ast.Module) -> list[tuple[int, str]]:
    """Every `<x>.tab_btns[...]` subscript inside a `nav_targets` body."""
    found = []
    declarations = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == _DECLARATION
    ]
    for declaration in declarations:
        for node in ast.walk(declaration):
            if not isinstance(node, ast.Subscript):
                continue
            target = node.value
            if isinstance(target, ast.Attribute) and target.attr == _RUN_ATTRIBUTE:
                found.append((node.lineno, ast.unparse(node)))
    return found


class TestTheTabRunIsNeverCutUp:
    """Slicing it by hand is what drops a view out of a ring."""

    def test_only_the_whole_run_and_archive_are_sliced(self):
        offenders = []
        for path in sorted(_UI.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for lineno, written in _tab_run_slices(tree):
                if written not in _ALLOWED:
                    offenders.append(f"{path.relative_to(_ROOT)}:{lineno}: {written}")

        assert not offenders, (
            "The button run is being sliced by hand. Whatever the slices leave "
            "out is a view missing from that page's keyboard ring, which shows "
            "up as the ring jumping a button on screen and shows up nowhere "
            "else. Take the run whole and use `tab_icons.stops_before` to put "
            "anything into it.\n" + "\n".join(offenders)
        )
