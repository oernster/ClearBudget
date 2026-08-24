"""Every theme token the UI asks for must exist in both themes.

Written after the whole `cell_*` family was deleted as dead. Nothing appeared
to read them: a search for `cell_ample_bg` found no consumer and neither
stylesheet contained the value, because the one consumer built the key as
`f"cell_{band}_bg"` and painted a table cell through QColor rather than QSS.
The app then raised KeyError the moment a card projection was drawn, which
left a process running with no window and the single-instance lock held.

A grep proves nothing about a key that is assembled at runtime. This scans the
source instead, so a token cannot be removed while a view still asks for it.
The UI layer is omitted from coverage, so a source scan is how its contract
with the theme gets pinned at all.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from clear_budget.ui.theme_tokens import DARK, LIGHT
from clear_budget.ui.views._credit_card_projection_strip import (
    _BAND_AMPLE,
    _BAND_TIGHT,
    _BAND_WATCH,
)

_UI_ROOT = Path(__file__).resolve().parents[2] / "clear_budget" / "ui"

# The names a theme token dict travels under in this layer: `theme.colours()`
# assigned locally, the copy a painted widget keeps and the two parameters the
# stylesheet builders take.
_TOKEN_DICT_NAMES = frozenset({"colours", "tokens", "_tokens", "t"})


def _token_keys_asked_for() -> set[tuple[str, str, int]]:
    """Return every (key, file, line) the UI reads from a token dict."""
    found: set[tuple[str, str, int]] = set()
    for path in sorted(_UI_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            if not isinstance(node.slice, ast.Constant):
                continue
            if not isinstance(node.slice.value, str):
                continue
            target = node.value
            name = None
            if isinstance(target, ast.Name):
                name = target.id
            elif isinstance(target, ast.Attribute):
                name = target.attr
            elif isinstance(target, ast.Call):
                func = target.func
                name = func.attr if isinstance(func, ast.Attribute) else None
            if name in _TOKEN_DICT_NAMES:
                found.add((node.slice.value, path.name, node.lineno))
    return found


def test_the_two_themes_carry_the_same_keys() -> None:
    """A token present in one theme and not the other is a crash waiting."""
    assert set(DARK) == set(LIGHT)


def test_every_token_the_ui_reads_exists_in_both_themes() -> None:
    """No view may ask for a token that has been renamed or removed."""
    asked = _token_keys_asked_for()
    assert asked, "the scan found no token reads, so it is not scanning"
    missing = sorted(
        f"{key} ({file}:{line})"
        for key, file, line in asked
        if key not in DARK or key not in LIGHT
    )
    assert not missing, "tokens read by the UI but absent from a theme: " + ", ".join(
        missing
    )


@pytest.mark.parametrize("band", [_BAND_TIGHT, _BAND_WATCH, _BAND_AMPLE])
def test_every_projection_band_paints_from_a_real_token(band: tuple[str, str]) -> None:
    """The credit-headroom bands name their tokens, so the scan can see them."""
    for key in band:
        assert key in DARK
        assert key in LIGHT
