"""The installer's sun/moon theme toggle, borrowed from the application.

The button used to carry the words "Dark Theme" and "Light Theme". The
application has said the same thing with a sun and a moon since it had a
theme at all, so the installer was the odd one out: the first window a user
sees, telling them in words what every window after it tells them in a
picture.

Both the faces and the tooltips are READ FROM the application rather than
copied here; the artwork is the same two files the app's tray wears, rendered
through the application's own crop-and-fit helper. That is the point
of the module: a second copy of "which face means which mode" is a copy that
eventually disagrees; the two would part company in the one place a user
compares them directly, having just watched the installer hand over to the
app. The two PNGs are bundled with the setup program for that reason (see
buildinstaller.py); a missing one leaves the button working, with its tooltip
as its label.

The face shows the mode a press switches TO, never the mode now in force.
That is the application's convention and reversing it here would make the
same picture mean opposite things in two windows of the same product.
"""

from __future__ import annotations

# Painted height of the picture inside its button. Smaller than the button so
# the face sits in the fill rather than filling it edge to edge.
GLYPH_PX = 20
# The button is a circle of this diameter, matching the height the Licence
# pill beside it takes from its own padding, so the two read as a pair.
BUTTON_PX = 36


def apply_toggle_face(btn, theme) -> None:
    """Put `theme`'s toggle face on `btn`: glyph, tooltip and shape.

    Called on build and again after every switch, because the face changes
    with the theme. It is fitted to `GLYPH_PX` by height, the same rule the
    application's tray uses, so the two shapes agree with each other.

    Falls back to the TOOLTIP as text when the artwork cannot be resolved, on
    the same grounds as the application's tray: a missing asset should cost
    the button its polish, never its function.
    """
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QIcon

    from clear_budget.ui.utils.icon_buttons import image_icon_pixmap

    btn.setFixedSize(BUTTON_PX, BUTTON_PX)
    btn.setToolTip(theme.toggle_tooltip)
    pixmap = image_icon_pixmap(theme.toggle_icon, GLYPH_PX)
    if pixmap is None:
        btn.setIcon(QIcon())
        btn.setText(theme.toggle_tooltip)
        return
    btn.setText("")
    btn.setIcon(QIcon(pixmap))
    btn.setIconSize(QSize(pixmap.width(), pixmap.height()))
