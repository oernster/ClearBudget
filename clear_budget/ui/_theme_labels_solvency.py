"""The Solvency view's own label roles, split from `_theme_labels`.

A cohesive concern rather than an arbitrary slice: every rule here belongs to
one view; they are also the only label roles in the application that carry a
traffic-light STATE as a Qt property, so the theme supplies the fill and a live
theme switch reaches them without any view holding a colour.

They left `_theme_labels` when documenting the banner and the headline pushed
that file into the size cap's danger band. Interpolated in place by the caller,
because QSS is order sensitive.

The three sizes this block shares with its parent are PARAMETERS rather than a
second copy of the constants. A number read from two modules that must never
disagree does not survive living in both of them.
"""

from __future__ import annotations

from clear_budget.shared import palette
from clear_budget.ui import ui_scale
from clear_budget.ui.theme_tokens import (
    STATE_AT_RISK,
    STATE_CAUTION,
    STATE_RED,
    STATE_SAFE,
)

# The caution amber is a light fill in both themes, so its banner takes dark
# text where the other states take the usual white.
_BANNER_FG_ON_CAUTION = palette.GREY_05
# Measured, not chosen. At 22 the Account Position banner needed 1074px for a
# routine Caution line and clipped inside a 1132px window; 20 brings that to
# 977px. The banner also WRAPS now, which is what makes it clip-proof at any
# width: no readable size fits its longest wording, which needs about 1470px
# here and would want 10px to fit the 860px minimum window.
_BANNER_FONT_PX = 20
# The Safe to Spend headline keeps the size the banner gave up. It shows a
# figure rather than a sentence; it is also the one number its page exists to
# state.
_HEADLINE_FONT_PX = 22


def solvency_label_roles_qss(
    t: dict[str, str],
    s: dict[str, str],
    *,
    section_px: int,
    breakdown_px: int,
    heading_px: int,
) -> str:
    """The Solvency view's label roles, ready to interpolate in place."""
    banner = ui_scale.px(_BANNER_FONT_PX)
    headline = ui_scale.px(_HEADLINE_FONT_PX)
    return f"""
/* Solvency view lines, each with its own weight in the reading order. The
   banner carries its traffic-light state as a Qt property, so the fill comes
   from the theme's state palette instead of an inline stylesheet and follows a
   live theme switch. Caution is a light fill in both themes, so it alone takes
   dark text.

   Two labels wear this shape and they are deliberately DIFFERENT SIZES, which
   is why the headline has a role of its own rather than sharing the banner's.
   The Account Position banner reports a sentence and had to come down to fit
   one; the Safe to Spend headline is a figure and stays at the size that makes
   it the loudest thing on its page. Sharing one role meant shrinking the
   headline to solve the banner's problem, which is two decisions taken as one.

   Everything except the size is shared, so the two cannot drift apart on fill,
   padding or the traffic-light states. The shared block deliberately sets NO
   font-size, so the two size rules never compete and neither depends on the
   order they are interpolated in (verified by moving one above the other and
   re-measuring: both labels kept their size). Putting a size back into the
   shared block is what would make order matter, since two id selectors carry
   equal specificity and the later one would then win. */
QLabel#SolvencyBanner,
QLabel#SafeToSpendHeadline {{
    font-weight: bold;
    padding: 10px;
    border-radius: 5px;
    color: {t["primary_text"]};
}}

QLabel#SolvencyBanner {{
    font-size: {banner}px;
}}

QLabel#SafeToSpendHeadline {{
    font-size: {headline}px;
}}

QLabel#SolvencyBanner[state="{STATE_RED}"],
QLabel#SafeToSpendHeadline[state="{STATE_RED}"] {{
    background-color: {s[STATE_RED]};
}}

QLabel#SolvencyBanner[state="{STATE_AT_RISK}"],
QLabel#SafeToSpendHeadline[state="{STATE_AT_RISK}"] {{
    background-color: {s[STATE_AT_RISK]};
}}

QLabel#SolvencyBanner[state="{STATE_CAUTION}"],
QLabel#SafeToSpendHeadline[state="{STATE_CAUTION}"] {{
    background-color: {s[STATE_CAUTION]};
    color: {_BANNER_FG_ON_CAUTION};
}}

QLabel#SolvencyBanner[state="{STATE_SAFE}"],
QLabel#SafeToSpendHeadline[state="{STATE_SAFE}"] {{
    background-color: {s[STATE_SAFE]};
}}

/* The mid-month dip line carries its state the same way the banner does, so
   a dip that stays inside an arranged overdraft is not painted in the red
   reserved for a bounced payment. The base rule keeps the strong danger fill
   as the fallback: the line is hidden unless there IS a dip, so the worse
   reading is the safer default if a state ever fails to resolve. */
QLabel#SolvencyMidmonthAlert {{
    font-size: {section_px}px;
    font-weight: bold;
    padding: 8px;
    border-radius: 5px;
    background-color: {t["danger_strong"]};
    color: {t["primary_text"]};
}}

QLabel#SolvencyMidmonthAlert[state="{STATE_RED}"] {{
    background-color: {s[STATE_RED]};
}}

QLabel#SolvencyMidmonthAlert[state="{STATE_AT_RISK}"] {{
    background-color: {s[STATE_AT_RISK]};
}}

QLabel#SolvencySectionHeading {{
    font-size: {heading_px}px;
    font-weight: bold;
}}

QLabel#SolvencyCommitted {{
    font-size: {section_px}px;
    padding: 5px;
    color: {t["text_muted"]};
}}

/* A shortfall no amount of restraint can close is the one line on the view
   that reports a fact rather than a caution, so it takes the traffic light's
   own red rather than the muted body colour it used to share with the reach
   sentence above it. */
/* The projection page's gap specification: what has to arrive for the page to
   come true. Italic because it is the one block there that is not yet a fact;
   neutral in colour because a list of expectations has no traffic-light state
   of its own, unlike the months below it. */
QLabel#SolvencyAssumedNote {{
    font-size: {section_px}px;
    padding: 5px;
    font-style: italic;
    color: {t["text_muted"]};
}}

QLabel#SolvencyShortfall {{
    font-size: {section_px}px;
    padding: 5px;
    color: {s[STATE_RED]};
}}

QLabel#SolvencyRemainingBank {{
    font-size: {section_px}px;
    padding: 5px;
    color: {t["warn"]};
}}

QLabel#SolvencyRemainingCard {{
    font-size: {section_px}px;
    padding: 5px;
    color: {t["warn_strong"]};
}}

QLabel#SolvencyBreakdown {{
    font-size: {breakdown_px}px;
    padding: 5px;
    color: {t["text_muted"]};
}}
"""
