"""The tab strip's icons: six bundled images, matched in size.

The primary view buttons carry pictures rather than words. The words are not
gone, they moved into the tooltips, so the strip still names itself to anyone
who pauses on a button; what went is a row of text labels wide enough to push
the strip most of the way across the window.

Four were PNGs and the archive was an emoji, which was the whole difficulty
here: they are different KINDS of image and Qt sizes them by different rules,
so the two families never agreed without measuring what each actually painted.
The archive is a picture now and that difficulty went with it. What remains is
one deliberate asymmetry:

* an image is fitted by its HEIGHT and then scaled up slightly, rather than
  fitted to a square box by its longer side. By the longer side the calendar
  came out 42 tall and the cards 35 against the emoji's 46, so the pictures
  sat visibly small beside the glyphs and worse, their BASES sat high: a row
  of icons that do not share a bottom edge reads as badly set rather than as
  differently sized. Fitting by height puts every icon on one baseline by
  construction. It does let the landscape card artwork run wider than its
  neighbours, which is accepted deliberately: a shared bottom edge is what the
  eye actually checks along a row.

Everything is cached per (spec, height): the source PNGs are the full-size
masters, so the crop and the downscale are worth doing once rather than on
every theme switch and rebuild.
"""

from __future__ import annotations

# Painted size of a view-button icon, before UI scaling, as the side of the square box
# each one is fitted into.
TAB_ICON_PX = 26
# A view-button icon paints this multiple of the box it is given. 1.0 because the box
# ALREADY carries the scale: `nav_glyph_size.NAV_GLYPH_SCALE` used to live here
# and lift the view buttons alone, which is exactly what left every other icon in the
# tray a third smaller than the buttons sitting beside them. Scaling here again
# would restore that gap in the other direction.
TAB_IMAGE_SCALE = 1.0
# The views, in strip order. Each entry is a bundled image filename, so adding
# a view means adding one line here and nothing else.
MONTHLY_BUDGET_ICON = "monthlybudget.png"
SOLVENCY_ICON = "solvency.png"
CREDIT_CARDS_ICON = "creditcards.png"
# The app icon. This view was an icon button wearing exactly this picture
# before it joined the run, so the move changed where it sits and what it
# does, never what it looks like.
GRAPH_ICON = "ClearBudget_256.png"
# What would make the months ahead survivable; sits right of the graph.
RECOMMENDATIONS_ICON = "recommendations.png"
# The last of the originals to stop being an emoji. A filing cabinet glyph was
# line work with space in it and read light beside the dense pictograms.
ARCHIVE_ICON = "archive.png"

# View names, so a view that needs to name one does not spell it again.
CREDIT_CARDS_TAB = "Credit Cards"
# The strip, in order, as (icon spec, the name that becomes the tooltip).
TAB_SPECS = (
    (MONTHLY_BUDGET_ICON, "Monthly Budget"),
    (SOLVENCY_ICON, "Solvency"),
    (CREDIT_CARDS_ICON, CREDIT_CARDS_TAB),
    (GRAPH_ICON, "Graph"),
    (RECOMMENDATIONS_ICON, "Recommendations"),
    (ARCHIVE_ICON, "Archive"),
)
# QSS hooks: the object name carrying the three-state ring rules, plus the
# dynamic property the stylesheet reads to mark the view being shown.
TAB_BUTTON_ROLE = "NavTabButton"
TAB_CURRENT_PROPERTY = "currentTab"

# Cache of built pixmaps, keyed by (spec, height). Qt objects, so this cannot
# be a functools cache built at import time: it needs a QApplication alive.
_PIXMAP_CACHE: dict[tuple[str, int], object] = {}


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


def tab_icon_pixmap(spec: str, box_px: int):
    """Return the pixmap for one view; None when its source is unavailable.

    None rather than a placeholder: a missing asset must leave the view usable
    (it keeps its tooltip and its place on the ring) rather than stop the
    window being built, which is the rule every other asset lookup follows.
    """
    key = (spec, box_px)
    if key in _PIXMAP_CACHE:
        return _PIXMAP_CACHE[key]
    pixmap = _image_pixmap(spec, box_px)
    _PIXMAP_CACHE[key] = pixmap
    return pixmap


def tab_icon(spec: str, box_px: int):
    """Return the QIcon for one view; None when its source is unavailable."""
    from PySide6.QtGui import QIcon

    pixmap = tab_icon_pixmap(spec, box_px)
    return None if pixmap is None else QIcon(pixmap)


def tab_icon_box_px() -> int:
    """The square box every view-button icon is fitted into, at the current UI scale."""
    from clear_budget.ui import ui_scale

    return max(1, ui_scale.px(TAB_ICON_PX))


def build_tab_buttons(box_px: int) -> list:
    """Return the primary view buttons, in strip order.

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
            # No artwork: the button keeps its NAME rather than becoming a blank
            # square. A missing asset costs the tray its looks, never a route
            # into the view.
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


def tab_button(buttons, label: str):
    """The button for the view called `label`; None when there is none.

    By NAME rather than by position, so a view that needs to put a stop
    beside a particular view says which view it means.
    """
    for position, (_spec, name) in enumerate(TAB_SPECS):
        if name == label and position < len(buttons):
            return buttons[position]
    return None


def stops_before(run: list, marker, extras: list) -> list:
    """`run` with `extras` inserted before `marker`; appended without it.

    Pure list work, deliberately: it is what lets a view insert its own
    controls into the button run WITHOUT slicing the run by hand. Slicing is
    what dropped the Graph button out of the Solvency ring entirely, since
    `[:2] + [2:3] + [-1:]` covers four of five positions and nothing says so.
    Everything in `run` is in the result, which is the property that matters
    and the one the hand-sliced version could not state.
    """
    if marker in run:
        at = run.index(marker)
        return run[:at] + extras + run[at:]
    return run + extras


def mark_current_tab(buttons, index: int) -> None:
    """Mark button `index` as the view being shown, clearing the others.

    Through a dynamic property and a repolish rather than an inline
    stylesheet, so a live theme switch restyles it: an inline colour would
    survive the switch and leave the mark painted in the outgoing theme.

    The current view's button is deliberately NOT disabled to make it inert. A disabled
    control paints the permanent red ring of the three-state model, which
    reads as broken rather than as current; it is dropped from the ring
    declaration instead, which is where "not a stop" belongs.
    """
    for i, button in enumerate(buttons):
        button.setProperty(TAB_CURRENT_PROPERTY, i == index)
        button.style().unpolish(button)
        button.style().polish(button)


def ring_tab_stops(buttons) -> list:
    """The view buttons that are keyboard-ring stops: every one but the current.

    The button already showing is not a stop. Landing on it would spend a
    keypress to highlight the page the user is looking at, which is precisely
    the dead stop `NavTabBar`'s separate cursor was built to avoid back when
    these were a `QTabBar`. The rule survived the widget it was written for.
    """
    return [b for b in buttons if not b.property(TAB_CURRENT_PROPERTY)]
