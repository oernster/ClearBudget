"""The tab strip's icons: three bundled images and one emoji, matched in size.

The four primary tabs carry pictures rather than words. The words are not
gone, they moved into the tooltips, so the strip still names itself to anyone
who pauses on a tab; what went is a row of four text labels wide enough to
push the strip most of the way across the window.

Three of the four are bundled PNGs and the fourth is an emoji, which is the
whole difficulty here. They are different KINDS of image and Qt sizes them by
different rules: a PNG has real pixels to scale, while a glyph is laid out by
a font's em box, which no emoji actually fills (see `glyph_metrics`). Sized
naively the two families never agree, so everything below reduces both to the
same question, "how tall does this thing actually PAINT", answering it by
measuring painted pixels in both cases.

Two deliberate asymmetries survive that:

* an image is fitted to a SQUARE box by its longer side, not by its height.
  The credit-card artwork is landscape where the other two are square; matching
  heights would have made it half again as wide as its neighbours,
  which reads as the strip's most important tab rather than its third.
* the emoji is measured by HEIGHT rather than fitted to the box, because the
  archive glyph is a tall narrow shape: fitted by its longer side it would
  paint 26 tall and about 17 wide, so it would already be the lightest thing
  on the strip. `nav_header.TOGGLE_GLYPH_SCALE` takes the opposite decision
  for the theme toggle and the difference is the glyph, not the rule: a sun
  is a solid saturated disc that fills its outline and looks heavy at equal
  size, where a filing cabinet is line work with space in it and looks light.
  Optical weight is what the eye compares, so the constant follows the glyph.

Everything is cached per (spec, height): the source PNGs are the full-size
masters, so the crop and the downscale are worth doing once rather than on
every theme switch and rebuild.
"""

from __future__ import annotations

# Painted size of a tab icon, before UI scaling, as the side of the square box
# each one is fitted into.
TAB_ICON_PX = 26
# An emoji tab icon paints at this fraction of the box's HEIGHT. 1.0 because
# the archive glyph is narrow line work and reads light beside three solid
# pictograms; see the module docstring for why this lands the opposite way
# round from `nav_header.TOGGLE_GLYPH_SCALE`.
TAB_EMOJI_SCALE = 1.0

# The four tabs, in strip order. An entry is either a bundled image filename
# or an emoji glyph; `_is_image` tells them apart by the suffix, so adding a
# tab means adding one line here and nothing else.
MONTHLY_BUDGET_ICON = "monthlybudget.png"
SOLVENCY_ICON = "solvency.png"
CREDIT_CARDS_ICON = "creditcards.png"
ARCHIVE_ICON = "\U0001f5c4️"

# Cache of built pixmaps, keyed by (spec, height). Qt objects, so this cannot
# be a functools cache built at import time: it needs a QApplication alive.
_PIXMAP_CACHE: dict[tuple[str, int], object] = {}


def _is_image(spec: str) -> bool:
    """Whether `spec` names a bundled image rather than being an emoji."""
    return spec.endswith(".png")


def _image_pixmap(spec: str, box_px: int):
    """Return the bundled image `spec` cropped and fitted to a `box_px` square.

    Cropped to its opaque content first, because the artwork carries its own
    transparent margins and they differ per file: fitting the raw canvas would
    size each icon by however much empty space its author left around it.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPixmap

    from clear_budget.shared.resources import find_tab_icon_path
    from clear_budget.ui.utils.glyph_metrics import opaque_bounding_rect

    path = find_tab_icon_path(spec)
    if path is None:
        return None
    image = QImage(str(path))
    if image.isNull():
        return None
    cropped = image.copy(opaque_bounding_rect(image))
    if cropped.isNull() or cropped.width() <= 0 or cropped.height() <= 0:
        return None
    pixmap = QPixmap.fromImage(cropped)
    # By the LONGER side, so a landscape image shares the square box with its
    # portrait and square neighbours instead of overrunning them.
    if pixmap.width() >= pixmap.height():
        return pixmap.scaledToWidth(box_px, Qt.TransformationMode.SmoothTransformation)
    return pixmap.scaledToHeight(box_px, Qt.TransformationMode.SmoothTransformation)


def _emoji_pixmap(glyph: str, box_px: int):
    """Return `glyph` painted `TAB_EMOJI_SCALE` of `box_px` tall, cropped tight.

    The font size comes from a measurement of this glyph rather than from the
    target, since an emoji paints a fraction of its em box that varies by
    glyph; the canvas is then cropped to the opaque pixels so the icon carries
    no padding of its own and Qt centres what was actually drawn.
    """
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap

    from clear_budget.ui.utils.glyph_metrics import (
        glyph_font_px_for_height,
        opaque_bounding_rect,
    )

    target = max(1, round(box_px * TAB_EMOJI_SCALE))
    font_px = glyph_font_px_for_height(glyph, target)
    side = font_px * 3
    canvas = QImage(side, side, QImage.Format.Format_ARGB32)
    canvas.fill(QColor(0, 0, 0, 0))
    font = QFont()
    font.setPixelSize(font_px)
    painter = QPainter(canvas)
    painter.setFont(font)
    painter.drawText(QRect(0, 0, side, side), Qt.AlignmentFlag.AlignCenter.value, glyph)
    painter.end()
    content = opaque_bounding_rect(canvas)
    if content.width() <= 0 or content.height() <= 0:
        return None
    return QPixmap.fromImage(canvas.copy(content))


def tab_icon_pixmap(spec: str, box_px: int):
    """Return the pixmap for one tab; None when its source is unavailable.

    None rather than a placeholder: a missing asset must leave the tab usable
    (it keeps its tooltip and its place on the ring) rather than stop the
    window being built, which is the rule every other asset lookup follows.
    """
    key = (spec, box_px)
    if key in _PIXMAP_CACHE:
        return _PIXMAP_CACHE[key]
    pixmap = (
        _image_pixmap(spec, box_px) if _is_image(spec) else _emoji_pixmap(spec, box_px)
    )
    _PIXMAP_CACHE[key] = pixmap
    return pixmap


def tab_icon(spec: str, box_px: int):
    """Return the QIcon for one tab; None when its source is unavailable."""
    from PySide6.QtGui import QIcon

    pixmap = tab_icon_pixmap(spec, box_px)
    return None if pixmap is None else QIcon(pixmap)


def tab_icon_box_px() -> int:
    """The square box every tab icon is fitted into, at the current UI scale."""
    from clear_budget.ui import ui_scale

    return max(1, ui_scale.px(TAB_ICON_PX))
