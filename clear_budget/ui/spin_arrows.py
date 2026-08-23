"""Arrow images for the spin-box buttons, generated per theme colour.

Qt gives a stylesheet exactly one way to put a glyph in a spin-box arrow:
`image: url(...)` pointing at a real file. The CSS triangle trick (`width: 0`
plus transparent side borders) is a browser idiom Qt does not implement; it
honours the zero size, draws nothing and leaves the button box behind, which
is what made the year pickers show two empty rectangles. Measured: with the
triangle rules the up button was 366 pixels of one flat colour; with an image
it carries the arrow.

Shipping the images as assets would mean one file per colour per theme, kept
in step with the palette by hand and added to every packaging script. They are
drawn here instead, into the app data directory, then cached under a filename
made from the colour and size. A new theme colour simply produces a new file
the first time it is used; nothing has to be remembered.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap, QPolygonF

from clear_budget.shared.config import Config
from clear_budget.ui import ui_scale

_DIR_NAME = "arrows"
# Unscaled arrow size. Wide enough to read as a triangle rather than a dot,
# short enough for two to sit inside a normal field height.
_WIDTH_PX = 10
_HEIGHT_PX = 7
# Inset so antialiasing has a pixel to work with instead of clipping the edge.
_EDGE = 0.5


def _arrows_dir() -> Path:
    return Config.app_dir() / _DIR_NAME


def _draw(path: Path, *, colour: str, up: bool, width: int, height: int) -> None:
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(colour))
    left, right = _EDGE, width - _EDGE
    top, bottom = _EDGE, height - _EDGE
    middle = width / 2
    points = (
        [(left, bottom), (right, bottom), (middle, top)]
        if up
        else [(left, top), (right, top), (middle, bottom)]
    )
    painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in points]))
    painter.end()
    pixmap.save(str(path))


def arrow_url(colour: str, *, up: bool) -> str:
    """A QSS-ready url() path to an arrow in `colour`, drawing it if needed.

    Cached by colour and size, so a theme switch reuses the file it made the
    first time and a palette change simply produces a new one.
    """
    width, height = ui_scale.px(_WIDTH_PX), ui_scale.px(_HEIGHT_PX)
    name = f"{'up' if up else 'down'}-{colour.lstrip('#')}-{width}x{height}.png"
    path = _arrows_dir() / name
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _draw(path, colour=colour, up=up, width=width, height=height)
        except OSError:
            # Best effort: without the file the arrow is simply absent, which
            # is no worse than the state this replaced.
            return ""
    # QSS wants forward slashes even on Windows.
    return path.as_posix()


def arrow_size() -> tuple[int, int]:
    """The (width, height) the stylesheet should reserve for an arrow."""
    return ui_scale.px(_WIDTH_PX), ui_scale.px(_HEIGHT_PX)
