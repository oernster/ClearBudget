"""Switching tabs must not cost the tray a control or leave a stray ring.

Two invariants, both broken at once when the graph icon moved down into the
lower tray.

The first is the TAB RUN. Every view builds its own tray, so a view that
simply never calls a builder loses that control silently: the tray still
draws, the app still runs and the capability is just gone from that tab.
Solvency lost the graph exactly that way and Archive never had it, which
changed the row's shape on the way in. Every view that draws a tray must
build the shared controls AND list them as keyboard stops, since a control
the ring skips is one the keyboard cannot reach.

The graph itself is no longer one of those controls. It was an icon button
that opened a modal dialog, which is what made it the odd one out; it is a
PAGE now, so what guards it is the tab wiring below rather than a per-view
button. What replaced those assertions is stronger than what they said: the
tab buttons are mapped onto the pages BY POSITION, each button index handed
straight to `setCurrentIndex`, so the strip and the pages agreeing is not a
tidiness question. A page inserted in the wrong slot silently points every
tab button in the application at the wrong page, while nothing about the tray
looks any different.

The second is the NEUTRAL START on a switch. Switching tabs hides the control
that was clicked; Qt then hands its focus to whatever comes next in the newly
shown page's chain. That control then paints the green focus ring, which sits
beside the current tab's accent border and reads as two tabs being current at
once. `MainWindow` already owns a 0x0 focus sink for the neutral start on
launch; the switch has to return to it.

Asserted by source scan because the suite is deliberately Qt-free (see
tests/conftest.py); a widget-level test would need a real window. The
behaviour itself is verified by an offscreen probe.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_UI = _ROOT / "clear_budget" / "ui"
_NAV_MIXIN = _UI / "_main_window_nav.py"
_MAIN_WINDOW = _UI / "_main_window_tabs.py"
_TAB_ICONS = _UI / "utils" / "tab_icons.py"

# Every view that draws a nav tray. All of them draw the SAME shortcuts, so a
# view that skips one loses that shortcut on that tab alone and nowhere else,
# which reads as the button having moved rather than as a defect.
_TRAY_VIEWS = (
    _UI / "views" / "_month_view_builders.py",
    _UI / "views" / "solvency_panel.py",
    _UI / "views" / "credit_card_view.py",
    _UI / "views" / "graph_view.py",
    _UI / "views" / "archive_view.py",
)

# Where each view's ring order is declared, when that is not the same file.
_RING_DECLARATIONS = {
    "_month_view_builders.py": _UI / "views" / "month_view.py",
}

_USERS_BUILDER = "build_users_button"
_USERS_ATTR = "users_btn"
_TABS_BUILDER = "build_tab_buttons"
_TABS_ATTR = "tab_btns"
_SINK = "_focus_sink"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _assigns_from_call(tree: ast.Module, attr: str, func: str) -> bool:
    """True if `self.<attr>` is assigned the result of calling `<func>`."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        call = node.value
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)):
            continue
        if call.func.id != func:
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr == attr:
                return True
    return False


def _self_attrs_returned_by(tree: ast.Module, method: str) -> set[str]:
    """Every `self.<name>` mentioned inside `method`, however it is spelled."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == method):
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Attribute)
                and isinstance(inner.value, ast.Name)
                and inner.value.id == "self"
            ):
                names.add(inner.attr)
    return names


def _string_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level `NAME = "text"` assignments, so a label may be named."""
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
            continue
        if not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                found[target.id] = node.value.value
    return found


def _tab_spec_labels() -> list[str]:
    """The tab names declared in `TAB_SPECS`, in strip order.

    A label may be a literal or a module constant naming one, since a view
    that has to name a tab should not spell it a second time. An entry that
    is NEITHER is returned as a marker rather than skipped: skipping made a
    label the reader could not parse look like a tab that had disappeared
    from the strip, which is the failure this guard exists to report
    truthfully.
    """
    tree = _tree(_TAB_ICONS)
    constants = _string_constants(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(t, ast.Name) and t.id == "TAB_SPECS" for t in node.targets
        ):
            continue
        labels = []
        for entry in node.value.elts:
            if not isinstance(entry, ast.Tuple):
                labels.append("<unreadable entry>")
                continue
            label = entry.elts[1]
            if isinstance(label, ast.Constant):
                labels.append(label.value)
            elif isinstance(label, ast.Name) and label.id in constants:
                labels.append(constants[label.id])
            else:
                labels.append(f"<unreadable label: {ast.unparse(label)}>")
        return labels
    return []


def _added_page_labels() -> list[str]:
    """The page names passed to `tabs.addTab`, in the order they are added."""
    labels = []
    for node in ast.walk(_tree(_MAIN_WINDOW)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "addTab"):
            continue
        if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
            continue
        labels.append(node.args[1].value)
    return labels


def test_the_tab_strip_and_the_pages_are_the_same_list() -> None:
    """A tab button's index IS the page index, so the two lists must match.

    `_wire_tab_buttons` connects button `i` to `setCurrentIndex(i)`. A page
    added in a different order from `TAB_SPECS` therefore sends every tray in
    the application to the wrong page, with nothing on screen looking wrong.
    """
    specs = _tab_spec_labels()
    pages = _added_page_labels()
    assert specs, "TAB_SPECS could not be read, so this guard is checking nothing"
    assert specs == pages, (
        "the tab strip and the pages have drifted apart:\n"
        f"  TAB_SPECS: {specs}\n"
        f"  addTab   : {pages}\n"
        "every tab button is wired to its page BY POSITION, so a mismatch "
        "points the tray at the wrong page rather than showing an error"
    )


def test_every_tray_view_builds_the_tab_buttons() -> None:
    """A tray without the tab run is a page with no way out of itself."""
    for path in _TRAY_VIEWS:
        assert _assigns_from_call(_tree(path), _TABS_ATTR, _TABS_BUILDER), (
            f"{path.name} never assigns self.{_TABS_ATTR} from "
            f"{_TABS_BUILDER}(), so that tab cannot reach the others"
        )


def test_every_tray_view_rings_the_tab_buttons() -> None:
    """The keyboard must reach the tabs from every page, not just the mouse."""
    for path in _TRAY_VIEWS:
        ring_path = _RING_DECLARATIONS.get(path.name, path)
        stops = _self_attrs_returned_by(_tree(ring_path), "nav_targets")
        assert _TABS_ATTR in stops, (
            f"{ring_path.name}'s nav_targets() omits self.{_TABS_ATTR}, so the "
            "keyboard cannot reach the tabs that page draws"
        )


def test_a_tab_switch_returns_focus_to_the_neutral_sink() -> None:
    """`currentChanged` must reach a handler that focuses the sink."""
    tree = _tree(_NAV_MIXIN)
    handlers = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "connect"):
            continue
        signal = func.value
        if isinstance(signal, ast.Attribute) and signal.attr == "currentChanged":
            for arg in node.args:
                if isinstance(arg, ast.Attribute):
                    handlers.add(arg.attr)
    assert handlers, (
        f"{_NAV_MIXIN.name} never connects tabs.currentChanged, so a switch "
        "leaves focus on whatever the new page offered first"
    )
    focuses_sink = any(
        _SINK in _self_attrs_returned_by(tree, name) for name in handlers
    )
    assert focuses_sink, (
        "the tabs.currentChanged handler never touches "
        f"self.{_SINK}, so the new page does not start neutral"
    )


def test_every_tray_view_builds_the_users_icon() -> None:
    """Switching account is offered on every tab or it is offered on none."""
    for path in _TRAY_VIEWS:
        assert _assigns_from_call(_tree(path), _USERS_ATTR, _USERS_BUILDER), (
            f"{path.name} never assigns self.{_USERS_ATTR} from "
            f"{_USERS_BUILDER}(), so that tab alone cannot switch user"
        )


def test_every_tray_view_rings_the_users_icon() -> None:
    """The keyboard must reach it, since a skipped stop reads as no control."""
    for path in _TRAY_VIEWS:
        ring_path = _RING_DECLARATIONS.get(path.name, path)
        stops = _self_attrs_returned_by(_tree(ring_path), "nav_targets")
        assert _USERS_ATTR in stops, (
            f"{ring_path.name}'s nav_targets() omits self.{_USERS_ATTR}, so "
            "the keyboard cannot reach a button the tray draws"
        )
