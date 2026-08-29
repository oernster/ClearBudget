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

# Breathing room between the glyph and the hover or focus ring drawn around it,
# on every side. Zero: the view buttons carry none and their rings do not sit hard
# against the artwork, so the tray's icon buttons taking any made their boxes
# 8px taller than a view button's while holding an icon of exactly the same height. One
# band of controls wants one box size.
NAV_ICON_BTN_PADDING_PX = 0

# Every glyph in the tray paints this multiple of the measured box. Slightly
# over 1.0 because the view buttons' artwork is dense pictograms: at a height equal to
# an emoji's they read as the smaller of the two. It lived in `view_buttons` and
# applied to the view buttons alone, which is what left the tray's own icons a third
# smaller than the buttons beside them in the same band. It is the base now, so
# every icon in the tray is sized through it and they end up equal.
NAV_GLYPH_SCALE = 1.35

# The footer's glyph as a fraction of the tray's. The strip at the foot is
# subordinate to the band above it, which is the heaviest thing on the window,
# so two matching bands would weigh the layout down at both ends. Expressed
# against the tray's own measured height rather than as a second pixel number,
# so retuning the tray carries the footer with it and the two cannot drift.
FOOTER_GLYPH_NUMERATOR = 2
FOOTER_GLYPH_DENOMINATOR = 3


def nav_glyph_height(prev_btn) -> int:
    """The height every glyph in the nav tray is sized to.

    One source for the app icon, the theme toggle and every icon button in the
    tray, taken from the Previous button so the row reads as a single band.
    They are built in different functions, so deriving it twice is how they
    drifted apart.

    Scaled by `NAV_GLYPH_SCALE`, which the view buttons used to apply on their own.
    A 0.75 factor lived here briefly, while the view buttons were still a strip of their
    own and the tray was the heaviest band on the window. With the buttons now in
    the tray, the tray IS the band, so it scales UP rather than down and every
    icon in it is sized through the one number.
    """
    measured = (
        prev_btn.sizeHint().height() if prev_btn is not None else FALLBACK_ICON_PX
    )
    return max(1, round(measured * NAV_GLYPH_SCALE))


def footer_glyph_height(tray_glyph_px: int) -> int:
    """The footer's glyph height: two thirds of the tray's, from its measurement.

    Takes the measured tray height rather than measuring again, for the same
    reason `nav_glyph_height` exists at all: deriving one number twice is how
    the tray and the toggle drifted apart. It is plain arithmetic on an int, so
    the ratio is pinned without a QApplication (see tests/conftest.py).
    """
    scaled = tray_glyph_px * FOOTER_GLYPH_NUMERATOR // FOOTER_GLYPH_DENOMINATOR
    return max(1, scaled)


def nav_icon_button_size(
    glyph: str, glyph_height: int, measure_width=None
) -> tuple[int, int]:
    """The (width, height) an emoji tray button takes to hold `glyph`.

    Matched on HEIGHT and sized on WIDTH, which is the rule `view_buttons`
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
