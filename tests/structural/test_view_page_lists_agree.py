"""The three lists of views in `_main_window_views.py` must agree, in order.

That file names its views THREE times: once as `self.views.addTab(...)` calls
which fix the page positions, once in the tray-shortcut loop that wires Load,
Save, Switch Budget and the bank button; and once as the `_views` literal fed
to `_wire_view_buttons` and `_setup_keyboard_nav`. Nothing made them agree.

Reserves shipped in the first two and was missing from the third, which is not
a tidy-up: `_wire_view_buttons` connects a tray's buttons per view and
`_view_pages` is indexed by PAGE POSITION, so the omission left the Reserves
page with view buttons connected to nothing and shifted every ring after it by
one, with the last page falling off the end and getting no ring at all. It
presents to a user as "none of the buttons work", which is exactly how it was
reported.

`VIEW_SPECS` is the fourth statement of the same order and the one the strip
is drawn from, so it is the authority all three are checked against.

Asserted by source scan because the suite is deliberately Qt-free (see
tests/conftest.py).
"""

from __future__ import annotations

import ast
from pathlib import Path

from clear_budget.ui.utils.view_buttons import VIEW_SPECS

_ROOT = Path(__file__).resolve().parents[2]
_SOURCE = _ROOT / "clear_budget" / "ui" / "_main_window_views.py"

# The call that fixes a page's position, plus the positional list's name.
_ADD_TAB = "addTab"
_SCROLLABLE = "_scrollable"
_VIEWS_LIST = "_views"
# The methods the positional list is handed to. Both index it by page
# position, which is what makes a missing entry silent rather than loud.
_POSITIONAL_CONSUMERS = ("_wire_view_buttons", "_setup_keyboard_nav")


def _tree() -> ast.Module:
    return ast.parse(_SOURCE.read_text(encoding="utf-8"))


def _added_pages() -> list[tuple[str, str]]:
    """(view variable, page title) for each addTab call, in source order."""
    pages: list[tuple[str, str]] = []
    for node in ast.walk(_tree()):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != _ADD_TAB or len(node.args) != 2:
            continue
        wrapped, title = node.args
        if not (isinstance(title, ast.Constant) and isinstance(title.value, str)):
            continue
        if not (
            isinstance(wrapped, ast.Call)
            and isinstance(wrapped.func, ast.Attribute)
            and wrapped.func.attr == _SCROLLABLE
            and wrapped.args
            and isinstance(wrapped.args[0], ast.Name)
        ):
            continue
        pages.append((wrapped.args[0].id, title.value))
    return pages


def _positional_list() -> list[str]:
    """The names in the `_views = [...]` literal, in order."""
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if _VIEWS_LIST not in targets or not isinstance(node.value, ast.List):
            continue
        return [e.id for e in node.value.elts if isinstance(e, ast.Name)]
    return []


def _tray_loop_names() -> list[str]:
    """The names in the for-loop tuple that wires the shared tray shortcuts."""
    for node in ast.walk(_tree()):
        if not (isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple)):
            continue
        names = [e.id for e in node.iter.elts if isinstance(e, ast.Name)]
        if len(names) == len(node.iter.elts) and len(names) > 1:
            return names
    return []


def test_the_scan_still_finds_all_three_lists() -> None:
    """Every assertion below is vacuous if the shapes stop being recognised."""
    assert _added_pages(), f"no addTab({_SCROLLABLE}(...), title) calls found"
    assert _positional_list(), f"no `{_VIEWS_LIST} = [...]` literal found"
    assert _tray_loop_names(), "no tray-shortcut for-loop tuple found"


def test_the_positional_list_is_still_used_positionally() -> None:
    """The guard is pointless if nothing indexes the list by page any more."""
    source = _SOURCE.read_text(encoding="utf-8")
    for consumer in _POSITIONAL_CONSUMERS:
        assert f"{consumer}({_VIEWS_LIST})" in source, (
            f"{_VIEWS_LIST} is no longer handed to {consumer}; if the wiring "
            "changed shape, this guard needs rewriting rather than deleting"
        )


def test_every_page_is_in_the_positional_list_in_page_order() -> None:
    """A view missing here has dead buttons and somebody else's ring."""
    added = [name for name, _title in _added_pages()]
    assert _positional_list() == added, (
        f"`{_VIEWS_LIST}` is {_positional_list()} while the pages are added in "
        f"the order {added}. Both `_wire_view_buttons` and "
        "`_setup_keyboard_nav` index by page position, so any difference "
        "leaves a page with buttons wired to nothing and a ring belonging to "
        "another view"
    )


def test_every_page_gets_the_shared_tray_shortcuts() -> None:
    """A view left out of the loop silently loses Load, Save and the rest."""
    added = [name for name, _title in _added_pages()]
    assert _tray_loop_names() == added, (
        f"the tray-shortcut loop covers {_tray_loop_names()} while the pages "
        f"are {added}, so a view draws those buttons and connects none of them"
    )


def test_the_pages_match_the_strip_they_are_reached_from() -> None:
    """The buttons drive `setCurrentIndex` directly, so order is meaning."""
    titles = [title for _name, title in _added_pages()]
    assert titles == [name for _spec, name in VIEW_SPECS], (
        f"the pages are {titles} while the strip draws "
        f"{[name for _spec, name in VIEW_SPECS]}; each button hands its own "
        "index straight to setCurrentIndex, so a mismatch points every button "
        "after it at the wrong page"
    )
