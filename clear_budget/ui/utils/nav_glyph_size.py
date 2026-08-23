"""How big every glyph in the navigation tray is drawn.

One module because it is one number, read from two places that must never
disagree: `nav_header` sizes the app icon and the tray's icon buttons from it,
`nav_toggle` sizes the sun and the moon from it. They were split apart to keep
each module clear of the 400-line cap, so the size they share had to stop
living inside one of them.
"""

# Nav-icon height used when there is no Previous button to measure against.
FALLBACK_ICON_PX = 24
# Every tray glyph is drawn at this fraction of the Previous button's height.
# The buttons used to match that height exactly, which made the tray the
# heaviest band on the window: seven pictograms at text-row height, above a
# tab strip that is now pictograms too. Scaled down they read as chrome
# rather than as content. Applied once inside `nav_glyph_height`, so the app
# icon, the sun/moon toggle and the five icon buttons cannot drift apart.
NAV_GLYPH_SCALE = 0.75
# The nav icon buttons' chrome: 2px padding plus 2px border on each side (see
# QPushButton#NavGraphButton in _theme_controls). Added to the glyph height it
# gives every emoji tray button the same overall size as the app-icon button;
# fixing the size is what stops Qt's default push-button minimum width making
# an icon-sized control 80-odd pixels wide.
NAV_ICON_BTN_CHROME_PX = 8


def nav_glyph_height(prev_btn) -> int:
    """The height every glyph in the nav tray is sized to.

    One source for the app icon, the theme toggle and every icon button in the
    tray, taken from the Previous button so the row reads as a single band.
    They are built in different functions, so deriving it twice is how they
    drifted apart.

    `NAV_GLYPH_SCALE` is applied HERE rather than at each call site for the
    same reason: it is the one number the whole tray reads, so the icons can
    only ever be resized together.
    """
    base = prev_btn.sizeHint().height() if prev_btn is not None else FALLBACK_ICON_PX
    return max(1, round(base * NAV_GLYPH_SCALE))
