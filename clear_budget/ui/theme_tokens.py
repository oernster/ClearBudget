"""Semantic colour tokens for the two application themes.

Every colour the stylesheet builders (theme_qss / _theme_controls) and the
theme-aware inline styles use is named here once per theme. The keys are
semantic (what the colour is FOR), so the light theme is a second dict, not a
second stylesheet. The VALUES all come from `shared.palette`, which is the one
place a colour is allowed to be written down; a structural test fails the build
on a hex literal anywhere else.

Ring colours follow the app-wide three-state model: no ring at rest, the ring
token on hover or focus while enabled, the danger token permanently while
disabled. The ring is a near neutral rather than a hue, because it is CHROME:
it says the system is responding, while hue is left to mean something. That is
also why `accent` is a separate token even though the two were once one colour.
"""

from __future__ import annotations
from clear_budget.shared import palette

THEME_DARK = "dark"
THEME_LIGHT = "light"

DARK: dict[str, str] = {
    "window_bg": palette.GREY_05,
    "panel_bg": palette.MUTED_BLUE_18,
    "panel_alt_bg": palette.MUTED_BLUE_22,
    "inset_bg": palette.GREY_05,
    "calendar_nav_bg": palette.MUTED_BLUE_18,
    "border": palette.MUTED_BLUE_28,
    "separator": palette.BLUE_25,
    "selection_bg": palette.BLUE_25,
    "text": palette.GREY_91,
    "text_muted": palette.GREY_65,
    "text_disabled": palette.GREY_46,
    "checkbox_hover": palette.MUTED_BLUE_84,
    "accent": palette.VIOLET_85,
    "info": palette.CYAN_50,
    "ring": palette.MUTED_BLUE_84,
    "danger": palette.RED_71,
    "warn": palette.AMBER_56,
    "primary_bg": palette.INDIGO_55,
    "primary_hover": palette.BLUE_56,
    "primary_pressed": palette.BLUE_45,
    # The one white that does NOT collapse into `text`. A button label sits on
    # a saturated blue; the softer white measures 4.00:1 against the hover fill
    # where pure white measures 4.95:1. The collapse was worth making everywhere
    # else. Here it would cost the label its AA contrast.
    "primary_text": palette.GREY_100,
    "danger_btn_bg": palette.RED_31,
    "danger_btn_hover": palette.RED_24,
    "disabled_fill": palette.MUTED_BLUE_28,
    "scroll_handle": palette.GREY_65,
    "scroll_handle_hover": palette.MUTED_BLUE_84,
    "calendar_sel_text": palette.GREY_05,
    "input_bg": palette.MUTED_BLUE_18,
    "input_text": palette.GREY_91,
    "link": palette.BLUE_68,
    "link_hover": palette.BLUE_78,
    "text_subtle": palette.GREY_65,
    "warn_strong": palette.AMBER_50,
    "danger_strong": palette.RED_51,
    "hover_fill": palette.MUTED_BLUE_22,
    "pill_up_bg": palette.BLUE_25,
    "pill_down_bg": palette.ORANGE_26,
    "card_stat_bg": palette.MUTED_BLUE_18,
    "cell_tight_bg": palette.RED_31,
    "cell_watch_bg": palette.AMBER_50,
    "cell_ample_bg": palette.MUTED_VIOLET_25,
    "cell_tight_fg": palette.GREY_91,
    "cell_watch_fg": palette.GREY_05,
    "cell_ample_fg": palette.GREY_91,
    "bar_text": palette.GREY_91,
}

LIGHT: dict[str, str] = {
    "window_bg": palette.MUTED_BLUE_96,
    "panel_bg": palette.GREY_100,
    "panel_alt_bg": palette.GREY_91,
    "inset_bg": palette.GREY_91,
    "calendar_nav_bg": palette.GREY_91,
    "border": palette.MUTED_BLUE_84,
    "separator": palette.MUTED_BLUE_84,
    "selection_bg": palette.BLUE_87,
    "text": palette.MUTED_BLUE_11,
    "text_muted": palette.GREY_46,
    "text_disabled": palette.GREY_65,
    "checkbox_hover": palette.MUTED_BLUE_35,
    "accent": palette.PURPLE_47,
    "info": palette.SKY_32,
    "ring": palette.MUTED_BLUE_27_H215,
    "danger": palette.RED_51,
    "warn": palette.ORANGE_37,
    "primary_bg": palette.INDIGO_55,
    "primary_hover": palette.BLUE_56,
    "primary_pressed": palette.BLUE_45,
    "primary_text": palette.GREY_100,
    "danger_btn_bg": palette.RED_51,
    "danger_btn_hover": palette.RED_35,
    "disabled_fill": palette.GREY_84,
    "scroll_handle": palette.GREY_46,
    "scroll_handle_hover": palette.MUTED_BLUE_35,
    "calendar_sel_text": palette.GREY_100,
    "input_bg": palette.GREY_100,
    "input_text": palette.MUTED_BLUE_11,
    "link": palette.BLUE_53,
    "link_hover": palette.BLUE_48,
    "text_subtle": palette.GREY_46,
    "warn_strong": palette.ORANGE_37,
    "danger_strong": palette.RED_42,
    "hover_fill": palette.GREY_91,
    "pill_up_bg": palette.BLUE_48,
    "pill_down_bg": palette.ORANGE_37,
    "card_stat_bg": palette.GREY_100,
    "cell_tight_bg": palette.RED_94,
    "cell_watch_bg": palette.AMBER_89,
    "cell_ample_bg": palette.VIOLET_95,
    "cell_tight_fg": palette.RED_31,
    "cell_watch_fg": palette.ORANGE_26,
    "cell_ample_fg": palette.MUTED_VIOLET_45,
    "bar_text": palette.MUTED_BLUE_11,
}

# Chart series colours are DATA encodings, not chrome, so they are a separate
# per-theme palette: pastels read on a near-black canvas, saturated mid-tones
# read on a light one. Same hue order in both, so a series keeps its identity
# across a theme switch.
# The following curve is deliberately outside the series palette in both
# themes, so it never reads as one more plotted series.
CURVE_DARK = palette.FUCHSIA_73
CURVE_LIGHT = palette.FUCHSIA_40

# ROLE colours, for a chart plotting a SINGLE series. With one series there is
# nothing to tell apart, so the mark is free to say what it IS rather than
# which series it is: a line reads as a running balance, bars read as one day
# each.
#
# The LINE is blue and carries no verdict, because it runs through positive
# and negative days alike and must not flatter either. It was a pale sky blue
# and is now a deeper one, which holds the eye against the bars it crosses in
# bar mode rather than washing out over them.
#
# The BARS take the SAFE colour ONLY where the value is positive; a below-zero
# bar keeps the danger red it has always had. That is why the colour is honest
# here where it was not on the line: a safe-coloured bar is drawn only on a day
# the account really is in credit, so it states a fact about that day rather
# than a verdict on the month. The same colour as the LINE would have been the
# opposite, since one stroke spanning a month said "in credit" over days that
# were not.
#
# The bar colour was a bright mint green and is now a muted lavender. The green
# read as glare at a lightness of 52%; it was also the same literal as the focus
# ring, so neither role could move without dragging the other along. Splitting
# them is what let the ring go neutral and the bar go lavender in one pass.
#
# These do NOT apply to a multi-series chart (one series per credit card),
# where telling one card from another is the whole job and the palette does it.
CHART_LINE_DARK = palette.CYAN_48
CHART_LINE_LIGHT = palette.SKY_27
CHART_BAR_DARK = palette.VIOLET_74
CHART_BAR_LIGHT = palette.MUTED_VIOLET_45

# A day below zero but still inside an ARRANGED overdraft is amber, not red.
# The facility exists to absorb exactly that day, so calling it red says a
# payment bounced when nothing did; red is kept for a day past the agreed
# floor, where one would. This is the banner's own three-state reading applied
# to a bar (see _solvency_panel_narratives._state_key) and it takes the same
# at-risk amber, so one day of the graph and the banner above it never
# describe the same position in two different colours. With no facility
# arranged the floor is zero, so this colour never appears and a below-zero
# bar is red exactly as before.
CHART_BAR_WITHIN_DARK = palette.AMBER_50
CHART_BAR_WITHIN_LIGHT = palette.ORANGE_37

# The single-series curve follows the same days the line would, so it takes
# the line's blue. The multi-series curve keeps its own hue: with up to eight
# series on the axis it has to stay outside the palette or it reads as one
# more card.
SOLO_CURVE_DARK = CHART_LINE_DARK
SOLO_CURVE_LIGHT = CHART_LINE_LIGHT

# The first slot is a near neutral rather than a hue of its own. Every other
# slot carries a hue; a near neutral is told apart by SATURATION, which none of
# the other seven compete for. Slot four is the app's one lavender, the
# same colour the safe state and the single-series bars take: a solo chart and
# a multi-series chart never appear together, so they cannot be confused.
# Slot six was a teal and is an indigo, since the teal was retired app-wide.
SERIES_DARK = (
    palette.MUTED_BLUE_84,
    palette.BLUE_68,
    palette.AMBER_56,
    palette.VIOLET_74,
    palette.PINK_70,
    palette.INDIGO_74,
    palette.RED_71,
    palette.ORANGE_61,
)

SERIES_LIGHT = (
    palette.MUTED_BLUE_47,
    palette.BLUE_53,
    palette.ORANGE_44,
    palette.MUTED_VIOLET_45,
    palette.PINK_51,
    palette.INDIGO_59,
    palette.RED_51,
    palette.ORANGE_48,
)

# Solvency states. Like the series palette these are data colours, used both as
# a banner fill and as text on the window background, so each theme needs its
# own set to stay legible in the text role.
#
# Red and caution keep the warning colours convention gives them. SAFE does not
# answer with green: it is a muted lavender, which says "not one of the two
# warnings" without claiming a verdict of its own. Its light-theme twin is the
# same hue taken dark enough to stay readable on white.
STATE_RED = "red"
STATE_AT_RISK = "at_risk"
STATE_CAUTION = "caution"
STATE_SAFE = "safe"

STATES_DARK = {
    STATE_RED: palette.RED_71,
    STATE_AT_RISK: palette.AMBER_50,
    STATE_CAUTION: palette.AMBER_56,
    STATE_SAFE: palette.VIOLET_74,
}

STATES_LIGHT = {
    STATE_RED: palette.RED_51,
    STATE_AT_RISK: palette.ORANGE_40,
    STATE_CAUTION: palette.ORANGE_37,
    STATE_SAFE: palette.MUTED_VIOLET_45,
}

_TOKENS_BY_THEME = {THEME_DARK: DARK, THEME_LIGHT: LIGHT}
_SERIES_BY_THEME = {THEME_DARK: SERIES_DARK, THEME_LIGHT: SERIES_LIGHT}
_STATES_BY_THEME = {THEME_DARK: STATES_DARK, THEME_LIGHT: STATES_LIGHT}


def tokens_for(theme_name: str) -> dict[str, str]:
    """Return the token dict for `theme_name`, defaulting to dark."""
    return _TOKENS_BY_THEME.get(theme_name, DARK)


def series_colours_for(theme_name: str) -> tuple[str, ...]:
    """Return the chart series palette for `theme_name`, defaulting to dark."""
    return _SERIES_BY_THEME.get(theme_name, SERIES_DARK)


def chart_line_colour_for(theme_name: str) -> str:
    """The line colour for a chart plotting one series."""
    return CHART_LINE_LIGHT if theme_name == THEME_LIGHT else CHART_LINE_DARK


def chart_bar_colour_for(theme_name: str) -> str:
    """The bar fill for a chart plotting one series (negatives stay danger)."""
    return CHART_BAR_LIGHT if theme_name == THEME_LIGHT else CHART_BAR_DARK


def chart_bar_within_facility_colour_for(theme_name: str) -> str:
    """The bar fill for a day inside an arranged overdraft, not past it."""
    return (
        CHART_BAR_WITHIN_LIGHT if theme_name == THEME_LIGHT else CHART_BAR_WITHIN_DARK
    )


def solo_curve_colour_for(theme_name: str) -> str:
    """The following curve over a single series' bars."""
    return SOLO_CURVE_LIGHT if theme_name == THEME_LIGHT else SOLO_CURVE_DARK


def curve_colour_for(theme_name: str) -> str:
    """Return the chart following-curve colour, defaulting to dark."""
    return CURVE_LIGHT if theme_name == THEME_LIGHT else CURVE_DARK


# How far an ASSUMED figure's colour is blended toward the page background.
# Assumed data has to read as provisional at a glance without changing what it
# means, so the hue is kept and only the presence is reduced: the same traffic
# light, spoken more quietly. Derived rather than hand-picked, so the muted set
# cannot drift from the real one if a state colour is ever changed; it also
# keeps new colour literals out of the file.
_ASSUMED_BLEND = 0.45


def _blend(colour: str, toward: str, fraction: float) -> str:
    """Mix `colour` toward `toward` by `fraction`, as a #rrggbb string."""
    a = tuple(int(colour[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(toward[i : i + 2], 16) for i in (1, 3, 5))
    mixed = (round(x + (y - x) * fraction) for x, y in zip(a, b))
    return "#" + "".join(f"{value:02x}" for value in mixed)


def assumed_state_colours_for(theme_name: str) -> dict[str, str]:
    """The traffic-light palette for figures that depend on assumed income.

    Same hues as `state_colours_for`, blended toward the page background so an
    assumed figure never competes with a known one for attention.
    """
    background = tokens_for(theme_name)["window_bg"]
    return {
        state: _blend(colour, background, _ASSUMED_BLEND)
        for state, colour in state_colours_for(theme_name).items()
    }


def state_colours_for(theme_name: str) -> dict[str, str]:
    """Return the solvency state palette for `theme_name`, defaulting to dark."""
    return _STATES_BY_THEME.get(theme_name, STATES_DARK)
