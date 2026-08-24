"""The sun/moon theme toggle: its glyph sizing and its button.

Split out of `nav_header` to keep both modules clear of the 400-line cap and
its danger band (`tests/structural/test_loc_limits.py`). One cohesive concern
lives here: how a two-faced emoji button is sized so that neither face looks
wrong beside the icon next to it. Every public name is re-exported by
`nav_header`, thence by `format_helpers`, so no call site moved.
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
# The toggle glyph's painted height as a fraction of the nav icon's.
#
# Deliberately NOT 1.0. Matching the two by measured height was tried and reads
# wrong: the sun and the moon are solid saturated shapes that fill their whole
# outline, while the nav icon is a pictogram with internal detail and light
# space in it, so equal heights leave the emoji looking the heavier of the two.
# Optical weight, not bounding box, is what the eye compares. The measurement
# machinery still matters underneath this, since it is what puts the sun and
# the moon on the same height as each other.
TOGGLE_GLYPH_SCALE = 0.8


def apply_toggle_glyph(btn, glyph: str) -> None:
    """Show `glyph` on a theme toggle, sized against the nav icon beside it.

    The painted height is `TOGGLE_GLYPH_SCALE` of the icon's, not equal to it;
    see that constant for why.

    Called on build and again after every theme switch, because the glyph
    changes with the theme and each one paints a different fraction of its em
    box: sizing the sun and then swapping in the moon leaves the moon short
    and sizing the moon leaves the sun oversized against the nav icon. The font
    size is therefore derived from THIS glyph every time, by measuring it.

    The font is set as a WIDGET-level stylesheet, not setFont: the app
    stylesheet sets a font-size on QWidget and a stylesheet rule beats setFont
    however specific the font is. A widget's own sheet beats the application's
    and setting only font-size leaves the object-name ring rules intact.

    SELECTOR REQUIRED. A bare `font-size: 42px` cascades to everything in the
    widget's subtree and a tooltip counts: the hover text came out in the
    emoji's size. Scoping it to the button means nothing else can inherit it.
    """
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QIcon

    from clear_budget.ui.utils.glyph_metrics import cropped_glyph_pixmap

    icon_height = btn.property(TOGGLE_TARGET_PROPERTY) or FALLBACK_ICON_PX
    target = max(1, round(int(icon_height) * TOGGLE_GLYPH_SCALE))
    pixmap = cropped_glyph_pixmap(glyph, target)
    if pixmap.isNull():
        btn.setText(glyph)
        return
    btn.setText("")
    btn.setIcon(QIcon(pixmap))
    btn.setIconSize(QSize(pixmap.width(), pixmap.height()))


def _build_theme_toggle_button(glyph_height: int):
    """Return the sun/moon theme toggle as a tabbable QPushButton.

    Object-name styled by the theme QSS (three-state ring, transparent
    fill). The glyph shows the mode a press switches TO; theme.apply_theme
    refreshes every toggle's glyph and tooltip after each switch.

    Sized from `glyph_height`, the same height the nav icon is scaled to, so
    the two read as a matched pair rather than the toggle looking like an
    afterthought beside it. That height rides on the button as a property, so
    the refresh after a theme switch can size the incoming glyph to it too.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QPushButton

    from clear_budget.ui import theme

    current = theme.current_theme(QApplication.instance())
    btn = QPushButton()
    btn.setObjectName("ThemeToggleButton")
    # Fixed size, like every other emoji tray button: without it Qt's default
    # push-button minimum width leaves a ring far wider than the sun. Sized to
    # the WIDER of the two faces, because this button's glyph changes under it
    # and a size taken from the sun alone would jump when the moon arrived.
    # Boxed at the tray's OWN glyph height, never at this button's reduced
    # one. TOGGLE_GLYPH_SCALE shrinks the sun and moon for optical weight;
    # sizing the box from that reduced figure shrank the button too, leaving
    # it visibly smaller than the buttons either side of it. The glyph is
    # drawn smaller inside a box that still matches its neighbours.
    faces = [nav_icon_button_size(face, glyph_height) for face in theme.toggle_glyphs()]
    btn.setFixedSize(max(w for w, _ in faces), max(h for _, h in faces))
    btn.setProperty(TOGGLE_TARGET_PROPERTY, glyph_height)
    apply_toggle_glyph(btn, theme.toggle_glyph(current))
    btn.setToolTip(theme.toggle_tooltip(current))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(lambda: theme.toggle_theme(QApplication.instance()))
    return btn
