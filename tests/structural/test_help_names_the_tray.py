"""Every tray button must be named on the How It Works screen.

The help screen's first job is naming the furniture, so a tray button it
does not mention is a picture with no caption anywhere in the application.
That is exactly how it went stale: the switch-user button was added to the
tray on every tab and the help screen carried on listing the row without it,
which read as the button being undocumented rather than as the guide being
behind.

Asserted by source scan because the suite is deliberately Qt-free (see
tests/conftest.py). The glyphs are matched as HTML numeric entities, since
that is how the help body spells them: the dialog builds one HTML string and
an entity survives the round trip through QTextBrowser where a raw astral
character in source would be easy to mistype invisibly.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_UI = _ROOT / "clear_budget" / "ui"
_TRAY = _UI / "widgets" / "_save_load_flow.py"
_HELP = _UI / "widgets" / "how_it_works_dialog.py"

# The factory every tray button is built through; its first argument is the
# glyph the button draws.
_BUTTON_FACTORY = "_tray_icon_button"
# Joins a base glyph to its variation selector, which the help body spells as
# a second entity (the settings cog is U+2699 U+FE0F, so "&#9881;&#65039;").
_VARIATION_SELECTOR = "️"


def _tray_glyphs() -> list[str]:
    """Every glyph passed as the first argument to the tray-button factory."""
    tree = ast.parse(_TRAY.read_text(encoding="utf-8"))
    glyphs = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != _BUTTON_FACTORY or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            glyphs.append(first.value)
    return glyphs


def _entities(glyph: str) -> str:
    """`glyph` as the run of HTML numeric entities the help body uses."""
    return "".join(f"&#{ord(char)};" for char in glyph)


def test_the_factory_is_still_the_only_way_in() -> None:
    """The scan is worthless if buttons stop coming through the factory."""
    glyphs = _tray_glyphs()
    assert len(glyphs) >= 1, (
        f"{_TRAY.name} builds no button through {_BUTTON_FACTORY}(), so this "
        "guard is scanning nothing and every other assertion here is vacuous"
    )


def test_the_help_screen_names_every_tray_button() -> None:
    """A button drawn in the tray must appear on the How It Works screen."""
    body = _HELP.read_text(encoding="utf-8")
    for glyph in _tray_glyphs():
        entities = _entities(glyph)
        bare = _entities(glyph.replace(_VARIATION_SELECTOR, ""))
        assert entities in body or bare in body, (
            f"the tray draws {glyph!r} ({entities}) but {_HELP.name} never "
            "names it, so the help screen is behind the tray again"
        )
