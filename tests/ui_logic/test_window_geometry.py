"""Qt-free tests for where a window is placed on a screen.

These carry more weight than usual. The behaviour they describe is
multi-monitor placement, which cannot be exercised on a one-screen machine
(the offscreen Qt platform reports a single display), so the arithmetic is
where the guarantee has to be pinned.

The rectangles are virtual-desktop coordinates, so a monitor left of or above
the primary one has a negative x or y. Those cases are the ones that break if
anyone reintroduces an assumption that a screen starts at (0, 0).
"""

import pytest

from clear_budget.ui._window_geometry import centred_position, default_window_rect

# A 1920x1080 monitor sitting to the LEFT of the primary one, with a taskbar
# taking 40px off the bottom: the shape that catches origin assumptions.
_LEFT_MONITOR = (-1920, 0, 1920, 1040)
_PRIMARY = (0, 0, 2560, 1400)
# A 34in ultrawide, the one screen wide enough that 33% clears the 860 floor.
_ULTRAWIDE = (0, 0, 3440, 1400)


def test_a_window_centres_on_the_screen_it_is_given():
    assert centred_position(available=_PRIMARY, size=(1000, 800)) == (780, 300)


def test_centring_carries_onto_a_monitor_at_negative_coordinates():
    """The left-hand monitor's origin is negative; the window must follow."""
    assert centred_position(available=_LEFT_MONITOR, size=(920, 840)) == (-1420, 100)


def test_centring_respects_a_taskbar_offset():
    """A screen whose usable area starts below the top places lower down."""
    available = (0, 60, 1920, 1020)
    assert centred_position(available=available, size=(920, 820)) == (500, 160)


def test_a_window_larger_than_the_screen_is_not_pushed_off_the_left():
    """Integer division of a negative overhang still lands on the screen."""
    x, _ = centred_position(available=_PRIMARY, size=(2560, 1400))
    assert x == 0


# The default main window: fractions on a big screen, floors on a small one.
def test_the_default_window_takes_its_fractions_on_a_wide_screen():
    """33% of 3440 clears the 860 floor, so the fraction is what applies."""
    rect = default_window_rect(
        available=_ULTRAWIDE,
        width_fraction=0.33,
        height_fraction=0.92,
        min_width=860,
        min_height=780,
    )
    assert rect == (1152, 56, 1135, 1288)


def test_the_width_floor_binds_before_the_fraction_does():
    """On 2560 across, 33% is 844, under the floor, so 860 wins."""
    _, _, width, _ = default_window_rect(
        available=_PRIMARY,
        width_fraction=0.33,
        height_fraction=0.92,
        min_width=860,
        min_height=780,
    )
    assert width == 860


def test_the_floors_bind_on_a_small_screen():
    """A 1280x720 laptop: the fractional size would clip the tables."""
    _, _, width, height = default_window_rect(
        available=(0, 0, 1280, 720),
        width_fraction=0.33,
        height_fraction=0.92,
        min_width=860,
        min_height=780,
    )
    assert (width, height) == (860, 720)


def test_the_window_never_exceeds_the_screen_it_is_placed_on():
    """The floors are capped by the display, so nothing overhangs it."""
    available = (0, 0, 800, 600)
    x, y, width, height = default_window_rect(
        available=available,
        width_fraction=0.33,
        height_fraction=0.92,
        min_width=860,
        min_height=780,
    )
    assert (width, height) == (800, 600)
    assert (x, y) == (0, 0)


@pytest.mark.parametrize("available", [_PRIMARY, _LEFT_MONITOR, (0, 60, 1920, 1020)])
def test_the_default_window_always_lands_inside_its_screen(available):
    """Whichever monitor it is given, the window sits within that monitor."""
    screen_x, screen_y, screen_w, screen_h = available
    x, y, width, height = default_window_rect(
        available=available,
        width_fraction=0.33,
        height_fraction=0.92,
        min_width=860,
        min_height=780,
    )
    assert screen_x <= x and x + width <= screen_x + screen_w
    assert screen_y <= y and y + height <= screen_y + screen_h
