"""Two thirds: the footer's glyph measured against the navigation tray's.

The strip at the foot is subordinate to the band above it: the tray is the
heaviest thing on the window by decision (`NAV_GLYPH_SCALE` is over 1.0 for
that reason), so a footer sized to match would weigh the layout down at both
ends. Two thirds reads as subordinate while leaving the artwork recognisable.

What these pin is that the RATIO is derived from the tray's own measurement
rather than written a second time as a pixel number. Measuring a glyph for real
needs a QPainter and this suite is Qt-free (see tests/conftest.py), so the
arithmetic is driven with heights stated outright, exactly as
`test_nav_icon_button_size` drives the button sizing.
"""

from __future__ import annotations

import pytest

from clear_budget.ui.utils.nav_glyph_size import (
    FOOTER_GLYPH_DENOMINATOR,
    FOOTER_GLYPH_NUMERATOR,
    footer_glyph_height,
)


def test_the_footer_takes_two_thirds_of_the_tray() -> None:
    """The ratio is the one decided, not merely some reduction."""
    assert (FOOTER_GLYPH_NUMERATOR, FOOTER_GLYPH_DENOMINATOR) == (2, 3)


@pytest.mark.parametrize(
    ("tray_px", "expected"),
    [
        (27, 18),  # the height measured on a real "← Previous" button
        (30, 20),
        (33, 22),
        (45, 30),
    ],
)
def test_two_thirds_of_the_measured_tray_height(tray_px: int, expected: int) -> None:
    """Whatever the tray measures, the footer is two thirds of it."""
    assert footer_glyph_height(tray_px) == expected


def test_the_ratio_holds_across_every_plausible_tray_height() -> None:
    """Stated as the property rather than as a table of four cases.

    The floor division is deliberate: a glyph is a whole number of pixels, so
    the footer rounds DOWN rather than landing half a pixel over its share.
    """
    for tray_px in range(1, 400):
        assert footer_glyph_height(tray_px) == max(1, tray_px * 2 // 3)


def test_a_tray_too_small_to_divide_still_leaves_a_glyph() -> None:
    """Two thirds of one pixel is none; a control with no artwork is not one.

    Unreachable at any real UI scale, which is why it is stated here rather
    than left to be discovered: the clamp is what stops a pathological scale
    turning the button into an empty box.
    """
    assert footer_glyph_height(1) == 1
    assert footer_glyph_height(0) == 1
