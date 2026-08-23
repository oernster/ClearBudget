"""Switching tabs must not cost the tray a control or leave a stray ring.

Two invariants, both broken at once when the graph icon moved down into the
lower tray.

The first is the GRAPH ICON. It is built per view, because every view builds
its own tray, so a view that simply never calls the builder loses the control
silently: the tray still draws, the app still runs and the capability is just
gone from that tab. Solvency lost it exactly that way. Every view that plots
something must build the button AND list it as a keyboard stop, since a
control the ring skips is one the keyboard cannot reach.

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

# Archive is absent on purpose: it plots nothing, so it has nothing to graph.
_PLOTTING_VIEWS = (
    _UI / "views" / "_month_view_builders.py",
    _UI / "views" / "solvency_panel.py",
    _UI / "views" / "credit_card_view.py",
)
# Where each view's ring order is declared, when that is not the same file.
_RING_DECLARATIONS = {
    "_month_view_builders.py": _UI / "views" / "month_view.py",
}

_BUILDER = "build_graph_icon_button"
_ATTR = "graph_btn"
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


def test_every_plotting_view_builds_the_graph_icon() -> None:
    """A view that plots must build its own graph button, not inherit one."""
    for path in _PLOTTING_VIEWS:
        assert _assigns_from_call(_tree(path), _ATTR, _BUILDER), (
            f"{path.name} never assigns self.{_ATTR} from {_BUILDER}(), so its "
            "tray silently loses the month graph"
        )


def test_every_plotting_view_rings_the_graph_icon() -> None:
    """The graph button must be a keyboard stop wherever it is drawn."""
    for path in _PLOTTING_VIEWS:
        ring_path = _RING_DECLARATIONS.get(path.name, path)
        stops = _self_attrs_returned_by(_tree(ring_path), "nav_targets")
        assert _ATTR in stops, (
            f"{ring_path.name}'s nav_targets() omits self.{_ATTR}, so the "
            "keyboard cannot reach a button the tray draws"
        )


def test_every_plotting_view_defines_the_graph_handler() -> None:
    """The button is wired to a handler that view actually owns."""
    for path in _PLOTTING_VIEWS:
        handler_path = _RING_DECLARATIONS.get(path.name, path)
        methods = {
            node.name
            for node in ast.walk(_tree(handler_path))
            if isinstance(node, ast.FunctionDef)
        }
        assert "on_show_graph" in methods, (
            f"{handler_path.name} builds a graph button with no on_show_graph "
            "to answer it"
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
