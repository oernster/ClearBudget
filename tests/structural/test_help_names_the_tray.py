"""Every picture button must be named on the How It Works screen.

The help screen's first job is naming the furniture, so a tray button it
does not mention is a picture with no caption anywhere in the application.
That is exactly how it went stale: the switch-user button was added to the
tray on every view and the help screen carried on listing the row without it,
which read as the button being undocumented rather than as the guide being
behind.

The window's FOOTER is scanned alongside the tray. It holds a button of its
own, in no tray at all, which is exactly the shape of thing this guard exists
to catch: a picture the user meets with no caption anywhere in the application.
Reading only `_tray_buttons.py` would have let it through.

The tray's buttons used to be emoji and are now bundled pictures, so the scan
follows both: a glyph is matched as the HTML numeric entities the help body
spells it with, a picture by the filename the help screen resolves to draw it
inline. An icon guide showing something other than the icon is worse than no
guide, which is why naming the button is not enough on its own.

Asserted by source scan because the suite is deliberately Qt-free (see
tests/conftest.py).
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_UI = _ROOT / "clear_budget" / "ui"
_TRAY = _UI / "widgets" / "_tray_buttons.py"
_FOOTER = _UI / "widgets" / "bottom_tray.py"
# Every source that builds a picture button the user can press. A new one goes
# here, which is the whole cost of keeping the guide honest about it.
_BUTTON_SOURCES = (_TRAY, _FOOTER)
_HELP = _UI / "widgets" / "how_it_works_dialog.py"

# The two factories a tray button is built through. The first argument of
# either is what the button DRAWS: an emoji, else the name of a constant
# holding a bundled picture's filename.
_GLYPH_FACTORY = "_tray_icon_button"
_IMAGE_FACTORY = "build_tray_image_button"
# Joins a base glyph to its variation selector, which the help body spells as
# a second entity (a settings cog was U+2699 U+FE0F, so "&#9881;&#65039;").
_VARIATION_SELECTOR = "️"


def _module_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level `NAME = "value"` assignments, so a spec can be resolved."""
    found: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not (
            isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        ):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                found[target.id] = node.value.value
    return found


def _tray_faces() -> tuple[list[str], list[str]]:
    """Return (glyphs, picture filenames) every scanned button is built with."""
    glyphs: list[str] = []
    pictures: list[str] = []
    for source in _BUTTON_SOURCES:
        _faces_in(ast.parse(source.read_text(encoding="utf-8")), glyphs, pictures)
    return glyphs, pictures


def _faces_in(tree: ast.Module, glyphs: list[str], pictures: list[str]) -> None:
    """Collect one module's button faces into the running lists."""
    constants = _module_constants(tree)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if node.func.id == _GLYPH_FACTORY:
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                glyphs.append(first.value)
        elif node.func.id == _IMAGE_FACTORY:
            if isinstance(first, ast.Name) and first.id in constants:
                pictures.append(constants[first.id])
            elif isinstance(first, ast.Constant) and isinstance(first.value, str):
                pictures.append(first.value)


def _entities(glyph: str) -> str:
    """`glyph` as the run of HTML numeric entities the help body uses."""
    return "".join(f"&#{ord(char)};" for char in glyph)


def test_the_factories_are_still_the_only_way_in() -> None:
    """The scan is worthless if buttons stop coming through a factory."""
    glyphs, pictures = _tray_faces()
    assert glyphs or pictures, (
        f"no scanned source builds a button through {_GLYPH_FACTORY}() or "
        f"{_IMAGE_FACTORY}(), so this guard is scanning nothing and every "
        "other assertion here is vacuous"
    )


def test_the_help_screen_names_every_tray_glyph() -> None:
    """A glyph drawn in a scanned source must appear on How It Works."""
    body = _HELP.read_text(encoding="utf-8")
    for glyph in _tray_faces()[0]:
        entities = _entities(glyph)
        bare = _entities(glyph.replace(_VARIATION_SELECTOR, ""))
        assert entities in body or bare in body, (
            f"the tray draws {glyph!r} ({entities}) but {_HELP.name} never "
            "names it, so the help screen is behind the tray again"
        )


def test_the_help_screen_draws_every_tray_picture() -> None:
    """A picture on a button must be the picture the help screen shows."""
    body = _HELP.read_text(encoding="utf-8")
    for filename in _tray_faces()[1]:
        assert f'"{filename}"' in body, (
            f"the tray draws {filename} but {_HELP.name} never resolves it, "
            "so the guide shows something other than the button it describes"
        )


def test_the_help_screen_has_stopped_naming_a_glyph_it_replaced() -> None:
    """A picture's old emoji must go; else the row lists the button twice."""
    body = _HELP.read_text(encoding="utf-8")
    retired = {
        "opendb.png": "\U0001f4c2",
        "savedb.png": "\U0001f4be",
        "information.png": "ℹ",
    }
    for filename, glyph in retired.items():
        if filename in body:
            assert _entities(glyph) not in body, (
                f"{_HELP.name} still draws {glyph!r} beside {filename}, so the "
                "tray row names one button as two"
            )
