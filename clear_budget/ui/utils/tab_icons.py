"""The tab strip's icons: four bundled images and one emoji, matched in size.

The primary tabs carry pictures rather than words. The words are not
gone, they moved into the tooltips, so the strip still names itself to anyone
who pauses on a tab; what went is a row of text labels wide enough to push
the strip most of the way across the window.

Four are bundled PNGs and one is an emoji, which is the whole difficulty
here. They are different KINDS of image and Qt sizes them by
different rules: a PNG has real pixels to scale, while a glyph is laid out by
a font's em box, which no emoji actually fills (see `glyph_metrics`). Sized
naively the two families never agree, so everything below reduces both to the
same question, "how tall does this thing actually PAINT", answering it by
measuring painted pixels in both cases.

Two deliberate asymmetries survive that:

* an image is fitted by its HEIGHT and then scaled up slightly, rather than
  fitted to a square box by its longer side. By the longer side the calendar
  came out 42 tall and the cards 35 against the emoji's 46, so the pictures
  sat visibly small beside the glyphs and worse, their BASES sat high: a row
  of icons that do not share a bottom edge reads as badly set rather than as
  differently sized. Fitting by height puts every icon on one baseline by
  construction. It does let the landscape card artwork run wider than its
  neighbours, which is accepted deliberately: a shared bottom edge is what the
  eye actually checks along a row.
* an emoji is measured by HEIGHT rather than fitted to the box, because the
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
# An image tab icon paints this multiple of the box's height. Slightly over
# 1.0 because these are dense pictograms sitting beside emoji that carry more
# light space: at equal heights the pictures read as the smaller of the two,
# which is the same optical-weight effect `TOGGLE_GLYPH_SCALE` corrects in the
# other direction on the theme toggle.
TAB_IMAGE_SCALE = 1.35
# The archive glyph paints this multiple of the box's height, matched to
# TAB_IMAGE_SCALE rather than left at the tray's own 1.0. Held equal on
# purpose: the three pictures grew past the tray's emoji; an archive glyph
# left behind at the smaller size stopped reading as their peer and started
# reading as the runt of the four. It is a tab first and an emoji second.
TAB_EMOJI_SCALE = TAB_IMAGE_SCALE

# The tabs, in strip order. An entry is either a bundled image filename
# or an emoji glyph; `_is_image` tells them apart by the suffix, so adding a
# tab means adding one line here and nothing else.
MONTHLY_BUDGET_ICON = "monthlybudget.png"
SOLVENCY_ICON = "solvency.png"
CREDIT_CARDS_ICON = "creditcards.png"
# The app icon. This tab was an icon button wearing exactly this picture
# before it became a tab, so becoming a tab changed where it sits and what it
# does, never what it looks like.
GRAPH_ICON = "ClearBudget_256.png"
ARCHIVE_ICON = "\U0001f5c4️"

# The strip, in order, as (icon spec, the name that becomes the tooltip).
TAB_SPECS = (
    (MONTHLY_BUDGET_ICON, "Monthly Budget"),
    (SOLVENCY_ICON, "Solvency"),
    (CREDIT_CARDS_ICON, "Credit Cards"),
    (GRAPH_ICON, "Graph"),
    (ARCHIVE_ICON, "Archive"),
)
# QSS hooks: the object name carrying the three-state ring rules, plus the
# dynamic property the stylesheet reads to mark the tab being shown.
TAB_BUTTON_ROLE = "NavTabButton"
TAB_CURRENT_PROPERTY = "currentTab"

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
    # By HEIGHT, so every icon in the row shares a bottom edge whatever its
    # aspect. Width is left to follow.
    target = max(1, round(box_px * TAB_IMAGE_SCALE))
    return pixmap.scaledToHeight(target, Qt.TransformationMode.SmoothTransformation)


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


def build_tab_buttons(box_px: int) -> list:
    """Return the primary tabs as icon buttons, in strip order.

    Buttons rather than a `QTabBar` because the tabs live in the navigation
    tray now, beside the database and settings shortcuts, rather than in a
    strip of their own. That SIMPLIFIES the keyboard model rather than
    complicating it: `NavTabBar` existed because Qt ties a tab bar's focus to
    its CURRENT tab, so a focused bar could only ever ring the tab the user
    was already on. A button carries no such tie. Walking the ring moves focus
    and changes nothing; Enter or Space activates and switches. That is
    exactly what the cursor was built to fake.

    Each button is sized to its OWN icon rather than to a shared square: the
    artwork differs in aspect and the icons are matched by painted HEIGHT,
    which is what puts them on one baseline (see `_image_pixmap`).
    """
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QPushButton

    from clear_budget.ui.utils.nav_glyph_size import NAV_ICON_BTN_CHROME_PX

    buttons = []
    for spec, label in TAB_SPECS:
        button = QPushButton()
        button.setObjectName(TAB_BUTTON_ROLE)
        button.setToolTip(label)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        pixmap = tab_icon_pixmap(spec, box_px)
        if pixmap is None:
            # No artwork: the tab keeps its NAME rather than becoming a blank
            # square. A missing asset costs the tray its looks, never a route
            # into the tab.
            button.setText(label)
        else:
            button.setIcon(QIcon(pixmap))
            button.setIconSize(QSize(pixmap.width(), pixmap.height()))
            button.setFixedSize(
                pixmap.width() + NAV_ICON_BTN_CHROME_PX,
                pixmap.height() + NAV_ICON_BTN_CHROME_PX,
            )
        buttons.append(button)
    return buttons


def mark_current_tab(buttons, index: int) -> None:
    """Mark button `index` as the tab being shown, clearing the others.

    Through a dynamic property and a repolish rather than an inline
    stylesheet, so a live theme switch restyles it: an inline colour would
    survive the switch and leave the mark painted in the outgoing theme.

    The current tab is deliberately NOT disabled to make it inert. A disabled
    control paints the permanent red ring of the three-state model, which
    reads as broken rather than as current; it is dropped from the ring
    declaration instead, which is where "not a stop" belongs.
    """
    for i, button in enumerate(buttons):
        button.setProperty(TAB_CURRENT_PROPERTY, i == index)
        button.style().unpolish(button)
        button.style().polish(button)


def ring_tab_stops(buttons) -> list:
    """The tab buttons that are keyboard-ring stops: every one but the current.

    The tab already showing is not a stop. Landing on it would spend a
    keypress to highlight the page the user is looking at, which is precisely
    the dead stop `NavTabBar`'s separate cursor was built to avoid back when
    these were a `QTabBar`. The rule survived the widget it was written for.
    """
    return [b for b in buttons if not b.property(TAB_CURRENT_PROPERTY)]
