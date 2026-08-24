"""How big every glyph in the navigation tray is drawn.

One module because it is one number, read from two places that must never
disagree: `nav_header` sizes the app icon and the tray's icon buttons from it,
`nav_toggle` sizes the sun and the moon from it. They were split apart to keep
each module clear of the 400-line cap, so the size they share had to stop
living inside one of them.
"""

# Nav-icon height used when there is no Previous button to measure against.
FALLBACK_ICON_PX = 24
# The nav icon buttons' chrome: 2px padding plus 2px border on each side (see
# QPushButton#NavGraphButton in _theme_controls). Added to the glyph height it
# gives every emoji tray button the same overall size as the app-icon button;
# fixing the size is what stops Qt's default push-button minimum width making
# an icon-sized control 80-odd pixels wide.
NAV_ICON_BTN_CHROME_PX = 8

# Breathing room between the glyph and the hover or focus ring drawn around
# it, on every side. The chrome above is the ring itself and the 2px the QSS
# already reserves; with only that, the ring sits hard against the artwork.
NAV_ICON_BTN_PADDING_PX = 4


def nav_glyph_height(prev_btn) -> int:
    """The height every glyph in the nav tray is sized to.

    One source for the app icon, the theme toggle and every icon button in the
    tray, taken from the Previous button so the row reads as a single band.
    They are built in different functions, so deriving it twice is how they
    drifted apart.

    Deliberately UNSCALED. A 0.75 factor lived here briefly, while the tabs
    were still a strip of their own and the tray was the heaviest band on the
    window. With the tabs now in the tray, the tray IS the band, so the icons
    are back at the height they started at.
    """
    return prev_btn.sizeHint().height() if prev_btn is not None else FALLBACK_ICON_PX


def nav_icon_button_size(
    glyph: str, glyph_height: int, measure_width=None
) -> tuple[int, int]:
    """The (width, height) an emoji tray button takes to hold `glyph`.

    Matched on HEIGHT and sized on WIDTH, which is the rule `tab_icons`
    already applies to the picture buttons: a shared height is what puts a row
    of differently-shaped icons on one baseline, while a shared WIDTH just
    squeezes the wide ones.

    Squeezing is not a cosmetic loss. Qt scales a colour-emoji bitmap down
    whole to fit the space it is given, so a glyph too wide for its button
    comes out short as well as narrow: measured on Windows at a 24px target,
    two busts drew 21px tall inside a square cut for a diskette, against the
    diskette's own 24. Giving each glyph the width it actually paints is what
    lets every one of them reach the same height.

    `measure_width` is the seam the arithmetic is tested through: measuring
    for real needs a QPainter and the suite is deliberately Qt-free.
    """
    if measure_width is None:
        from clear_budget.ui.utils.glyph_metrics import (
            glyph_painted_width_for_height as measure_width,
        )

    surround = 2 * NAV_ICON_BTN_PADDING_PX + NAV_ICON_BTN_CHROME_PX
    painted_width = measure_width(glyph, glyph_height)
    # Never narrower than tall: a narrow glyph keeps a square button rather
    # than becoming a slot, so the row still reads as a row of icons.
    return max(painted_width, glyph_height) + surround, glyph_height + surround
