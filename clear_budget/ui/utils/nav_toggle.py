"""The sun/moon theme toggle: its two faces and its button.

Split out of `nav_header` to keep both modules clear of the 400-line cap and
its danger band (`tests/structural/test_loc_limits.py`). One cohesive concern
lives here: how a TWO-FACED button is sized so that neither face looks wrong
beside the icon next to it, then how it avoids resizing under the user when
the face swaps. Every public name is re-exported by `nav_header`,
thence by `format_helpers`, so no call site moved.

The faces were emoji and are now bundled pictures, which removed a whole
class of problem rather than moving it: a glyph paints an unpredictable
fraction of its em box, so each one had to be measured and given its own font
size; the sun and moon also needed shrinking against the tray's pictograms for
optical weight. Two pictures drawn in the same style as the rest of the tray
simply take the tray's own height.
"""

# The nav-icon height used when there is no Previous button to measure
# against; kept in step with `nav_header.FALLBACK_ICON_PX`, which is the same
# number for the same reason and is imported rather than repeated.
from clear_budget.ui.utils.nav_glyph_size import (
    FALLBACK_ICON_PX,
    nav_icon_button_size,
)

# Dynamic property carrying the height a toggle button's glyph must paint at.
# Stored on the button because the glyph changes with the theme long after the
# tray was built and the refresh has only the button to work from.
TOGGLE_TARGET_PROPERTY = "navGlyphTargetPx"
# The toggle's painted height as a fraction of the nav icon's. 1.0 now the
# faces are pictures: they are drawn in the same style as every other icon in
# the tray, so they take the same height and the row reads as one band. It was
# 0.8 while they were emoji, because a solid saturated glyph looks heavier
# than a pictogram at equal size; that correction described the emoji, not the
# button, so it left with them.
TOGGLE_ICON_SCALE = 1.0


def apply_toggle_icon(btn, spec: str, tooltip: str) -> None:
    """Show the picture `spec` on a theme toggle, with its hover text.

    Called on build and again after every theme switch. The height comes from
    the property the button carries rather than from the incoming picture, so
    a face that is a different shape is fitted to the button rather than the
    button growing to fit it.

    The button's SIZE is deliberately not touched here: it was fixed at build
    time to the wider of the two faces, so swapping face cannot make the row
    reflow under the pointer.
    """
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QIcon

    from clear_budget.ui.utils.icon_buttons import image_icon_pixmap

    btn.setToolTip(tooltip)
    icon_height = btn.property(TOGGLE_TARGET_PROPERTY) or FALLBACK_ICON_PX
    target = max(1, round(int(icon_height) * TOGGLE_ICON_SCALE))
    pixmap = image_icon_pixmap(spec, target)
    if pixmap is None:
        # A missing picture leaves the control reachable and named, the rule
        # every other asset lookup in the tray follows.
        btn.setIcon(QIcon())
        btn.setText(tooltip)
        return
    btn.setText("")
    btn.setIcon(QIcon(pixmap))
    btn.setIconSize(QSize(pixmap.width(), pixmap.height()))


def _face_size(spec: str, glyph_height: int) -> tuple[int, int]:
    """The (width, height) a toggle button takes to hold the picture `spec`.

    Measured from the artwork rather than assumed square: the sun is wider
    than it is tall once cropped and the moon is not, so a square box would
    clip one of them.
    """
    from clear_budget.ui.utils.icon_buttons import image_icon_pixmap

    target = max(1, round(glyph_height * TOGGLE_ICON_SCALE))
    pixmap = image_icon_pixmap(spec, target)
    width = glyph_height if pixmap is None else pixmap.width()
    return nav_icon_button_size(spec, glyph_height, measure_width=lambda *_: width)


def _build_theme_toggle_button(glyph_height: int):
    """Return the sun/moon theme toggle as a tabbable QPushButton.

    Object-name styled by the theme QSS (three-state ring, transparent
    fill). The picture shows the mode a press switches TO; theme.apply_theme
    refreshes every toggle's face and tooltip after each switch.

    Sized from `glyph_height`, the same height the nav icon is scaled to, so
    the two read as a matched pair rather than the toggle looking like an
    afterthought beside it. That height rides on the button as a property, so
    the refresh after a theme switch can size the incoming face to it too.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QPushButton

    from clear_budget.ui import theme

    current = theme.current_theme(QApplication.instance())
    btn = QPushButton()
    btn.setObjectName("ThemeToggleButton")
    # Fixed size, like every other tray button: without it Qt's default
    # push-button minimum width leaves a ring far wider than the sun. Sized to
    # the WIDER of the two faces, because this button's picture changes under
    # it and a size taken from the sun alone would jump when the moon arrived.
    faces = [_face_size(spec, glyph_height) for spec in theme.toggle_icons()]
    btn.setFixedSize(max(w for w, _ in faces), max(h for _, h in faces))
    btn.setProperty(TOGGLE_TARGET_PROPERTY, glyph_height)
    apply_toggle_icon(btn, theme.toggle_icon(current), theme.toggle_tooltip(current))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(lambda: theme.toggle_theme(QApplication.instance()))
    return btn
