"""Every view button must be named on the How It Works screen.

The tray already has this guard (`test_help_names_the_tray.py`) and the view
strip did not, which is how the help screen came to announce six views while
the strip drew seven: Reserves shipped with a picture, a tooltip and no
caption anywhere in the application.

Two things go stale together, so both are asserted. The ROW: every entry in
`VIEW_SPECS` must have a `_view_row(...)` on the help screen built from the
same icon constant and carrying the same name, so the guide shows the picture
the button actually draws rather than a description of it. The HEADING: the
count it announces must be the number of buttons there are, because a heading
that miscounts is the first thing a reader checks the screen against.

Asserted by source scan because the suite is deliberately Qt-free (see
tests/conftest.py).
"""

from __future__ import annotations

import ast
from pathlib import Path

from clear_budget.ui.utils import view_buttons
from clear_budget.ui.utils.view_buttons import VIEW_SPECS

_ROOT = Path(__file__).resolve().parents[2]
_HELP = _ROOT / "clear_budget" / "ui" / "widgets" / "how_it_works_dialog.py"

# The one factory a view's help line is built through. Its first argument is
# the icon constant the strip draws and its second is the name the tooltip
# shows.
_ROW_FACTORY = "_view_row"
# The heading that opens the list, as a format string over the count word.
_HEADING = "<h3>The {} views</h3>"
# Index is the count, so `_COUNT_WORDS[7]` is "seven". Only as far as the
# strip could plausibly grow; a longer strip fails loudly here rather than
# quietly writing a digit into prose.
_COUNT_WORDS = (
    "",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
)


def _help_rows() -> dict[str, str]:
    """Return {icon filename: name} for every `_view_row(...)` on the screen."""
    tree = ast.parse(_HELP.read_text(encoding="utf-8"))
    rows: dict[str, str] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != _ROW_FACTORY or len(node.args) < 2:
            continue
        spec, name = node.args[0], node.args[1]
        if not isinstance(spec, ast.Name):
            continue
        if not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
            continue
        rows[getattr(view_buttons, spec.id)] = name.value
    return rows


def test_the_factory_is_still_the_only_way_in() -> None:
    """The scan is worthless if rows stop coming through the factory."""
    assert _help_rows(), (
        f"{_HELP.name} builds no line through {_ROW_FACTORY}(), so this guard "
        "is scanning nothing and every other assertion here is vacuous"
    )


def test_the_help_screen_draws_every_view_button() -> None:
    """A picture on the strip must be the picture the help screen shows."""
    rows = _help_rows()
    for spec, name in VIEW_SPECS:
        assert spec in rows, (
            f"the strip draws {spec} for {name} but {_HELP.name} never shows "
            "it, so the view has a picture and no caption anywhere in the app"
        )
        assert rows[spec] == name, (
            f"{_HELP.name} calls {spec} {rows[spec]!r} while the strip's "
            f"tooltip says {name!r}, so the guide names the button twice over"
        )


def test_the_help_screen_shows_no_view_the_strip_dropped() -> None:
    """A retired view left on the screen documents a button that is gone."""
    specs = {spec for spec, _ in VIEW_SPECS}
    for spec, name in _help_rows().items():
        assert spec in specs, (
            f"{_HELP.name} still shows {spec} as {name!r} but the strip no "
            "longer draws it, so the guide describes a button nobody has"
        )


def test_the_heading_counts_the_views_it_lists() -> None:
    """The screen announced six while the strip drew seven; never again."""
    body = _HELP.read_text(encoding="utf-8")
    count = len(VIEW_SPECS)
    assert count < len(_COUNT_WORDS), (
        f"the strip has grown to {count} buttons, past the words this guard "
        "knows; extend _COUNT_WORDS rather than writing a digit into prose"
    )
    assert _HEADING.format(_COUNT_WORDS[count]) in body, (
        f"{_HELP.name} does not head its list "
        f"{_HEADING.format(_COUNT_WORDS[count])!r}, so the screen miscounts "
        "the strip it is describing"
    )
