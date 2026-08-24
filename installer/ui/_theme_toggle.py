"""The installer's sun/moon theme toggle, borrowed from the application.

The button used to carry the words "Dark Theme" and "Light Theme". The
application has said the same thing with a sun and a moon since it had a
theme at all, so the installer was the odd one out: the first window a user
sees, telling them in words what every window after it tells them in a
picture.

Both the glyphs and the tooltips are READ FROM the application rather than
copied here; the emoji is rendered through the application's own cropped
pixmap helper. That is the point of the module: a second copy of "which face
means which mode" is a copy that eventually disagrees; the two would
part company in the one place a user compares them directly, having just watched
the installer hand over to the app.

The face shows the mode a press switches TO, never the mode now in force.
That is the application's convention and reversing it here would make the
same picture mean opposite things in two windows of the same product.
"""

from __future__ import annotations

# Painted height of the glyph inside its button. Smaller than the button so
# the emoji sits in the fill rather than filling it edge to edge; the sun and
# the moon are solid saturated shapes and read heavier than their box.
GLYPH_PX = 20
# The button is a circle of this diameter, matching the height the Licence
# pill beside it takes from its own padding, so the two read as a pair.
BUTTON_PX = 36


def apply_toggle_face(btn, theme) -> None:
    """Put `theme`'s toggle face on `btn`: glyph, tooltip and shape.

    Called on build and again after every switch, because the glyph changes
    with the theme. The pixmap is re-rendered each time rather than cached
    per face: each emoji paints a different fraction of its em box, so a size
    measured from the sun leaves the moon looking short.

    Falls back to the glyph as TEXT when the pixmap cannot be rendered, on
    the same grounds as the application's tray: a missing emoji font should
    cost the button its polish, never its function.
    """
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QIcon

    from clear_budget.ui.utils.glyph_metrics import cropped_glyph_pixmap

    btn.setFixedSize(BUTTON_PX, BUTTON_PX)
    btn.setToolTip(theme.toggle_tooltip)
    pixmap = cropped_glyph_pixmap(theme.toggle_glyph, GLYPH_PX)
    if pixmap.isNull():
        btn.setIcon(QIcon())
        btn.setText(theme.toggle_glyph)
        return
    btn.setText("")
    btn.setIcon(QIcon(pixmap))
    btn.setIconSize(QSize(pixmap.width(), pixmap.height()))
