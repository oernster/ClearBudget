"""How a nav-tray icon button is sized around the glyph it holds.

The rule these pin: the buttons match on HEIGHT and are sized on WIDTH. A row
of emoji is only on one baseline if every glyph reaches the same height; a
wide glyph only reaches it if its button is wide enough to hold it. Cut every
button to the same square and Qt shrinks the wide bitmaps whole to fit, so
they come out short as well as narrow; measured on Windows at a 24px target,
two busts drew 21px tall beside a diskette's 24.

Measuring a glyph for real needs a QPainter and this suite is Qt-free (see
tests/conftest.py), so the arithmetic is driven through the module's own
measurement seam with widths stated outright.
"""

from __future__ import annotations

from clear_budget.ui.utils.nav_glyph_size import (
    NAV_ICON_BTN_CHROME_PX,
    NAV_ICON_BTN_PADDING_PX,
    nav_icon_button_size,
)

_GLYPH_HEIGHT = 24
_SURROUND = 2 * NAV_ICON_BTN_PADDING_PX + NAV_ICON_BTN_CHROME_PX


def _measuring(width: int):
    """A stand-in measurer reporting `width` for whatever it is asked about."""

    def measure(glyph: str, target_px: int) -> int:
        return width

    return measure


def test_a_square_glyph_gets_a_square_button() -> None:
    """The common case; the one every other case is compared against."""
    size = nav_icon_button_size("x", _GLYPH_HEIGHT, _measuring(_GLYPH_HEIGHT))
    assert size == (_GLYPH_HEIGHT + _SURROUND, _GLYPH_HEIGHT + _SURROUND)


def test_a_wide_glyph_gets_a_wider_button_at_the_same_height() -> None:
    """The bug this exists for: the height must not move with the width."""
    wide = _GLYPH_HEIGHT + 8
    width, height = nav_icon_button_size("x", _GLYPH_HEIGHT, _measuring(wide))
    assert width == wide + _SURROUND
    assert height == _GLYPH_HEIGHT + _SURROUND


def test_every_button_in_a_row_shares_one_height() -> None:
    """Whatever the glyph paints, the baseline is the same."""
    heights = {
        nav_icon_button_size("x", _GLYPH_HEIGHT, _measuring(w))[1]
        for w in (8, _GLYPH_HEIGHT, _GLYPH_HEIGHT * 2)
    }
    assert len(heights) == 1


def test_a_narrow_glyph_still_gets_a_square_button() -> None:
    """A slot-shaped button would read as a different kind of control."""
    width, height = nav_icon_button_size("x", _GLYPH_HEIGHT, _measuring(6))
    assert width == height


def test_the_glyph_is_padded_on_every_side() -> None:
    """The point of the padding: the ring must not sit on the artwork."""
    wide = _GLYPH_HEIGHT + 8
    width, height = nav_icon_button_size("x", _GLYPH_HEIGHT, _measuring(wide))
    assert (width - wide) // 2 >= NAV_ICON_BTN_PADDING_PX
    assert (height - _GLYPH_HEIGHT) // 2 >= NAV_ICON_BTN_PADDING_PX
