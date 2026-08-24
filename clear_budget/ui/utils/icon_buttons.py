"""Bundled PICTURES used as button icons, matched to the tray's emoji.

`tab_icons` does this for the tab strip, at the tab run's own scale. This is
the same idea for the controls that are not tabs: the tray's Bank Account
button and the Graph page's bank/cards switch, both of which sit beside
emoji buttons and have to agree with them on height.

The crop matters more than it looks. Every source canvas carries its own
transparent margin and no two authors leave the same one, so fitting the raw
canvas would size each icon by however much empty space happens to surround
it. Cropping to the artwork first is what puts a row of different pictures on
one footing.

Which is also why PADDING CANNOT LIVE IN THE FILE. Adding transparent space
below the artwork in the PNG does nothing at all here: the crop is the first
thing that happens and it takes that space straight back off. Padding has to
be added after the crop, which is what `bottom_pad_px` is for.
"""

from __future__ import annotations


def image_icon_pixmap(spec: str, height_px: int, *, bottom_pad_px: int = 0):
    """`spec` cropped to its artwork and painted `height_px` tall; None if absent.

    None rather than a placeholder, the rule every other asset lookup here
    follows: a missing picture costs a control its looks, never its purpose.

    `bottom_pad_px` is transparent space added BELOW the artwork afterwards.
    It is measured in the same units as `height_px`, so the artwork is
    drawn that much shorter rather than the icon growing. That keeps the
    control the same size as its neighbours while lifting a flat-based
    picture off the bottom of its button.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

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
    artwork_px = max(1, height_px - max(0, bottom_pad_px))
    pixmap = QPixmap.fromImage(cropped).scaledToHeight(
        artwork_px, Qt.TransformationMode.SmoothTransformation
    )
    if bottom_pad_px <= 0:
        return pixmap
    padded = QPixmap(pixmap.width(), height_px)
    padded.fill(QColor(0, 0, 0, 0))
    painter = QPainter(padded)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return padded


def build_tray_image_button(
    spec: str, tooltip: str, glyph_height: int, *, bottom_pad_px: int = 0
):
    """A tray button carrying a bundled picture, sized like the emoji ones.

    Sized through `nav_icon_button_size`, the same arithmetic the emoji
    buttons use, with this picture's measured width standing in for the
    glyph's. Matching on HEIGHT and following on WIDTH is what keeps a row of
    differently shaped icons on one baseline.

    Returns a TEXT button carrying the tooltip when the artwork cannot be
    resolved, so a missing asset leaves the control reachable and named.
    """
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QPushButton

    from clear_budget.ui import label_roles
    from clear_budget.ui.utils.nav_glyph_size import nav_icon_button_size

    btn = QPushButton()
    btn.setToolTip(tooltip)
    btn.setObjectName(label_roles.ICON_ACTION)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    pixmap = image_icon_pixmap(spec, glyph_height, bottom_pad_px=bottom_pad_px)
    if pixmap is None:
        btn.setText(tooltip)
        return btn
    btn.setIcon(QIcon(pixmap))
    btn.setIconSize(QSize(pixmap.width(), pixmap.height()))
    btn.setFixedSize(
        *nav_icon_button_size(
            spec, glyph_height, measure_width=lambda *_: pixmap.width()
        )
    )
    return btn
