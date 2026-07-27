"""Window placement arithmetic. Pure Python, no Qt.

Where a window sits on a screen is arithmetic over rectangles, so it lives
here rather than inline in the composition root. That makes it testable
without a QApplication (tests/ui_logic/test_window_geometry.py), which
matters more than usual here: the multi-monitor behaviour this drives cannot
be exercised on a one-screen machine, so the maths is what gets pinned.

Rectangles are (x, y, width, height) in the virtual desktop's coordinate
space, the same space QScreen.availableGeometry() reports. A monitor left of
or above the primary one therefore has a negative x or y, and the arithmetic
carries a window onto it with no special case.
"""

from __future__ import annotations

Rect = tuple[int, int, int, int]


def centred_position(*, available: Rect, size: tuple[int, int]) -> tuple[int, int]:
    """The top-left that centres a window of `size` within `available`."""
    x, y, width, height = available
    window_width, window_height = size
    return (
        x + (width - window_width) // 2,
        y + (height - window_height) // 2,
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
