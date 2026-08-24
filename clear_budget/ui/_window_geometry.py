"""Window placement arithmetic. Pure Python, no Qt.

Where a window sits on a screen is arithmetic over rectangles, so it lives
here rather than inline in the composition root. That makes it testable
without a QApplication (tests/ui_logic/test_window_geometry.py), which
matters more than usual here: the multi-monitor behaviour this drives cannot
be exercised on a one-screen machine, so the maths is what gets pinned.

Rectangles are (x, y, width, height) in the virtual desktop's coordinate
space, the same space QScreen.availableGeometry() reports. A monitor left of
or above the primary one therefore has a negative x or y; the arithmetic
carries a window onto it with no special case.
"""

from __future__ import annotations

Rect = tuple[int, int, int, int]

# Default main-window geometry as a fraction of the available screen area. The
# fractions keep the window compact on a large monitor; the floors below
# guarantee the multi-column Bills and Income tables stay readable on a small
# one. They live here rather than in the composition root because they are
# inputs to the arithmetic below; a constant kept away from the sum that
# uses it is a constant that drifts from it.
WINDOW_WIDTH_FRACTION = 0.33
WINDOW_HEIGHT_FRACTION = 0.92

# Absolute floors in logical screen points, device-independent and so NOT
# scaled by the UI factor. They bind only on a small screen, where the
# fractional size would clip table columns; on a large screen the fractions
# already exceed them. Both are capped to the available area, so the window
# never exceeds the display.
MIN_WINDOW_WIDTH_PT = 860
MIN_WINDOW_HEIGHT_PT = 780

# The available-screen height that maps to a 1.0x UI scale. A taller screen
# scales the UI up to the cap; a shorter one scales it down, so the layout
# stays proportionate from a 13in laptop to a 4K display. The lower bound of
# 0.5x is enforced inside ui_scale.init().
UI_SCALE_REFERENCE_HEIGHT_PT = 1260.0
MAX_UI_SCALE_FACTOR = 1.5

# Index of the height element in an (x, y, width, height) rect.
AVAILABLE_HEIGHT = 3


def centred_position(*, available: Rect, size: tuple[int, int]) -> tuple[int, int]:
    """The top-left that centres a window of `size` within `available`.

    `size` is the window's FRAME, not its client area. Qt's move() positions
    the frame of a top-level window while setGeometry() positions the client
    rect inside it, so centring a client rect leaves the visible window high
    and left of centre by half the title bar and border.

    A window bigger than the screen is pulled back to the screen's own origin
    rather than centred to a negative offset, so its title bar stays reachable
    and the overhang all falls off the far edge.
    """
    x, y, width, height = available
    window_width, window_height = size
    return (
        max(x, x + (width - window_width) // 2),
        max(y, y + (height - window_height) // 2),
    )


def default_window_rect(
    *,
    available: Rect,
    width_fraction: float,
    height_fraction: float,
    min_width: int,
    min_height: int,
) -> Rect:
    """The default main-window rect, centred on `available`.

    The fractions keep the window compact on a large monitor, the floors keep
    it readable on a small one and both are capped to the screen, so the
    window never overhangs the display it was placed on.
    """
    _, _, screen_width, screen_height = available
    width = min(max(int(screen_width * width_fraction), min_width), screen_width)
    height = min(max(int(screen_height * height_fraction), min_height), screen_height)
    x, y = centred_position(available=available, size=(width, height))
    return (x, y, width, height)
