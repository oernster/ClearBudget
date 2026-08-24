"""Painted-pixel measurement for images and text glyphs.

Qt sizes text by the font's em box, never by what a glyph actually paints; and
emoji differ widely in how much of that box they fill. Measured on Windows at a
42px font: the sun paints 43px tall, the moon 38px, a 13% spread between the two
faces of the SAME button. A single fraction of the target height can therefore
only ever be right for one of them, which is how the theme toggle came to sit
larger than the nav icon beside it.

Everything here measures the real pixels instead, so a size is derived from the
glyph in hand rather than assumed for glyphs in general. That matters offscreen
too: the offscreen platform substitutes its own font database, where both glyphs
measure 38px, so a constant tuned under `QT_QPA_PLATFORM=offscreen` does not
describe what the user sees.
"""

from functools import cache

# Side of the scratch canvas a glyph is measured on, as a multiple of its font
# size. Emoji can paint outside their em box, so the canvas is given room on
# every side; a clipped glyph would measure short and be sized up to compensate.
_MEASURE_CANVAS_SCALE = 3


def opaque_bounding_rect(image):
    """Return the QRect bounding box of non-transparent pixels in `image`."""
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QImage

    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    width, height = image.width(), image.height()

    def row_has_content(y: int) -> bool:
        return any((image.pixel(x, y) >> 24) & 0xFF for x in range(width))

    def col_has_content(x: int) -> bool:
        return any((image.pixel(x, y) >> 24) & 0xFF for y in range(height))

    rows = [y for y in range(height) if row_has_content(y)]
    if not rows:
        return QRect(0, 0, 0, 0)
    cols = [x for x in range(width) if col_has_content(x)]
    return QRect(cols[0], rows[0], cols[-1] - cols[0] + 1, rows[-1] - rows[0] + 1)


def _render_glyph(glyph: str, font_px: int):
    """Paint `glyph` alone on a transparent canvas and return that QImage."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter

    font_px = max(1, font_px)
    side = font_px * _MEASURE_CANVAS_SCALE
    canvas = QImage(side, side, QImage.Format.Format_ARGB32)
    canvas.fill(QColor(0, 0, 0, 0))

    font = QFont()
    font.setPixelSize(font_px)
    painter = QPainter(canvas)
    painter.setFont(font)
    painter.drawText(QRect(0, 0, side, side), Qt.AlignmentFlag.AlignCenter.value, glyph)
    painter.end()
    return canvas


def cropped_glyph_pixmap(glyph: str, target_px: int):
    """Return `glyph` as a QPixmap cropped to the pixels it actually paints.

    Drawn as an ICON rather than left to Qt as button text, because Qt centres
    text by the FONT's em box and not by the artwork inside it. Reaching a
    given painted height needs a different font size for every emoji, so the
    em boxes differ in size too; the wide glyphs, which need the largest
    fonts, end up sitting lowest. Measured on Windows at a 30px target: two
    busts needed a 39px font and settled 6px below the centre of a button
    where a diskette at 30px sat 1px off it.

    Cropping to the opaque bounding box removes the em box from the question
    entirely. What is left is the artwork, which Qt then centres exactly.
    """
    from PySide6.QtGui import QPixmap

    canvas = _render_glyph(glyph, glyph_font_px_for_height(glyph, target_px))
    rect = opaque_bounding_rect(canvas)
    if rect.isEmpty():
        return QPixmap()
    return QPixmap.fromImage(canvas.copy(rect))


def painted_glyph_size(glyph: str, font_px: int) -> tuple[int, int]:
    """Return the (width, height) in pixels that `glyph` paints at `font_px`.

    Rendered to an off-screen ARGB canvas and measured by its opaque pixels,
    which is the only reading that accounts for a colour emoji font, where the
    glyph is a bitmap whose extents owe nothing to the font's own metrics.

    The WIDTH matters as much as the height. Emoji are not square: measured on
    Windows, two busts paint a third wider than they are tall, while a diskette
    is square. Fit such a glyph into a square cut for the diskette and the
    style shrinks the whole bitmap to make the width fit, so it loses height
    too and ends up visibly smaller than its neighbours.
    """
    rect = opaque_bounding_rect(_render_glyph(glyph, font_px))
    return rect.width(), rect.height()


def painted_glyph_height(glyph: str, font_px: int) -> int:
    """Return the height in pixels that `glyph` paints at a `font_px` font."""
    return painted_glyph_size(glyph, font_px)[1]


@cache
def glyph_font_px_for_height(glyph: str, target_px: int) -> int:
    """Return the font pixel size at which `glyph` paints `target_px` tall.

    The glyph is measured once at the target size, then the font is scaled by
    however far that reading missed. Emoji scale linearly with the font size, so
    one reading is enough and the target doubles as the reference, leaving no
    tuned constant to drift.

    A glyph that paints nothing (a missing font, a blank canvas) falls back to
    the target size, which is the answer the old fixed fraction gave.
    """
    target_px = max(1, int(target_px))
    painted = painted_glyph_height(glyph, target_px)
    if painted <= 0:
        return target_px
    return max(1, round(target_px * target_px / painted))


@cache
def glyph_painted_width_for_height(glyph: str, target_px: int) -> int:
    """Return the width `glyph` paints once scaled to `target_px` tall.

    What a button holding this glyph has to be wide enough for. Measured at
    the font size the height fit chose, so the two readings describe the same
    drawn glyph rather than two different ones.
    """
    return painted_glyph_size(glyph, glyph_font_px_for_height(glyph, target_px))[0]
