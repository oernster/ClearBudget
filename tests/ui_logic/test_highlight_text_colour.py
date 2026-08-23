"""Qt-free tests for one app-wide rule: highlight text is teal, never green.

Green belongs to the RING, the border that says where the pointer or the
keyboard is. The words inside that ring take the accent. Painting the text in
the ring's own green made a hovered tab read as a second, slightly different
selection sitting next to the real one, two greens a few degrees apart on the
same strip.

The rule was never about the tab bar, which is exactly why it outlived it. The
strip that provoked it is gone, the tabs being icon buttons in the navigation
tray now, yet the rule still binds every surface where a green ring goes round
TEXT: the menu bar and the menu items, which is what is asserted below. The
tab buttons carry no text, so there is nothing there for this rule to govern;
their ring and their current-tab mark are held by `_theme_controls` instead.

Asserted against the stylesheet these surfaces generate rather than a rendered
widget, for two measured reasons: a hover state cannot be forced through
`QWidget.render` (the hovered surface draws unhovered), plus the whole-sheet
`build_qss` cannot run here at all, since it resolves the system font and
generates the spin-box arrow images, both of which need a live QApplication.
The rules under test come from pure string builders that touch no Qt.
"""

import re

import pytest

from clear_budget.ui._theme_menus import menu_qss
from clear_budget.ui.theme_tokens import THEME_DARK, THEME_LIGHT, tokens_for

_THEMES = (THEME_DARK, THEME_LIGHT)

# Selector -> the builder whose sheet carries it.
_HIGHLIGHTS = {
    "QMenuBar::item:selected": menu_qss,
    "QMenu::item:selected": menu_qss,
}

# The highlights that put a green ring round the text: border and text differ.
_RINGED = (
    "QMenuBar::item:selected",
    "QMenu::item:selected",
)


def _rule_body(theme_name: str, selector: str) -> str:
    sheet = _HIGHLIGHTS[selector](tokens_for(theme_name))
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", sheet)
    assert match, f"{selector} is missing from the {theme_name} stylesheet"
    return " ".join(match.group(1).split())


def _declared(body: str, prop: str) -> str | None:
    match = re.search(rf"(?:^|[;{{]\s*|\s){re.escape(prop)}\s*:\s*([^;]+);", body)
    return match.group(1).strip() if match else None


@pytest.mark.parametrize("theme_name", _THEMES)
@pytest.mark.parametrize("selector", sorted(_HIGHLIGHTS))
def test_highlight_text_is_the_accent(theme_name, selector) -> None:
    body = _rule_body(theme_name, selector)
    assert _declared(body, "color") == tokens_for(theme_name)["accent"]


@pytest.mark.parametrize("theme_name", _THEMES)
@pytest.mark.parametrize("selector", sorted(_HIGHLIGHTS))
def test_no_highlight_paints_its_text_in_the_ring_colour(theme_name, selector) -> None:
    """The failure this file exists for, stated directly."""
    body = _rule_body(theme_name, selector)
    assert _declared(body, "color") != tokens_for(theme_name)["ring"]


@pytest.mark.parametrize("theme_name", _THEMES)
@pytest.mark.parametrize("selector", _RINGED)
def test_the_ring_around_that_text_stays_green(theme_name, selector) -> None:
    """Teal text, green border: the two must not collapse into one colour."""
    body = _rule_body(theme_name, selector)
    border = _declared(body, "border-color") or _declared(body, "border")
    assert tokens_for(theme_name)["ring"] in border


@pytest.mark.parametrize("theme_name", _THEMES)
def test_the_two_colours_are_actually_different(theme_name) -> None:
    """Nothing above means anything if the tokens are the same colour."""
    tokens = tokens_for(theme_name)
    assert tokens["accent"] != tokens["ring"]
