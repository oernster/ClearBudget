"""Slider-switch images for the card Active toggle, generated per theme colour.

The toggle is a QCheckBox whose indicator is drawn as a pill-and-knob slider
(the shape every music app uses for on/off) rather than the square tick box:
an on/off STATE reads as a switch, where a square reads as a selection mark.
Qt's stylesheet engine cannot draw the knob (a checkbox indicator has no
subcontrol for it), so the whole pill is an image, exactly as the spin-box
arrows are (see spin_arrows.py for why images rather than CSS shapes): drawn
into the app data directory and cached under a filename made from the colours
and size, so each theme produces its own files the first time it is used and
nothing ships or is hand-maintained.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap

from clear_budget.shared.config import Config
from clear_budget.ui import ui_scale

_DIR_NAME = "switches"
# Unscaled pill size; the knob fills the height minus the inset each side.
_WIDTH_PX = 36
_HEIGHT_PX = 18
_KNOB_INSET_PX = 2
# Inset so antialiasing has a pixel to work with instead of clipping the edge.
_EDGE = 0.5


def _switches_dir() -> Path:
    return Config.app_dir() / _DIR_NAME


def _draw(
    path: Path, *, track: str, knob: str, on: bool, width: int, height: int
) -> None:
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor(0, 0, 0, 0))
    painter.setBrush(QColor(track))
    radius = (height - 2 * _EDGE) / 2
    painter.drawRoundedRect(
        QRectF(_EDGE, _EDGE, width - 2 * _EDGE, height - 2 * _EDGE), radius, radius
    )
    inset = ui_scale.px(_KNOB_INSET_PX)
    diameter = height - 2 * inset
    x = (width - inset - diameter) if on else inset
    painter.setBrush(QColor(knob))
    painter.drawEllipse(QRectF(x, inset, diameter, diameter))
    painter.end()
    pixmap.save(str(path))


def switch_url(*, track: str, knob: str, on: bool) -> str:
    """A QSS-ready url() path to a switch image, drawing it if needed.

    Cached by colours, side and size, so a theme switch reuses the file it
    made the first time and a palette change simply produces a new one.
    """
    width, height = switch_size()
    side = "on" if on else "off"
    name = f"{side}-{track.lstrip('#')}-{knob.lstrip('#')}-{width}x{height}.png"
    path = _switches_dir() / name
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _draw(path, track=track, knob=knob, on=on, width=width, height=height)
        except OSError:
            # Best effort: without the file the toggle falls back to the bare
            # indicator box, which is no worse than the state this replaced.
            return ""
    # QSS wants forward slashes even on Windows.
    return path.as_posix()


def switch_size() -> tuple[int, int]:
    """The (width, height) the stylesheet should reserve for the pill."""
    return ui_scale.px(_WIDTH_PX), ui_scale.px(_HEIGHT_PX)
