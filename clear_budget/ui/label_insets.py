"""Every label's inset, by role: contents margins, never the stylesheet.

A word-wrapped QLabel given ANY box spacing by a stylesheet (padding or
margin, all four sides or only two) works out its height for a line that
needs a little more room than it paints with. Across a narrow band of widths
the label keeps a second row with nothing in it, so a box grows taller with
no extra text. That is how the Solvency banner came to be taller in one month
than the next (measured offscreen by counting the painted lines against the
box height: about 10px of label width in every case tried; the same inset
given as contents margins or as QLabel's own margin left no band at all).

So no label rule in the stylesheet carries padding or margin. The inset lives
here, keyed by the role a label already carries as its object name; the
application style applies it whenever a label is polished: when it is built,
when set_role swaps its role and when a theme is applied. No call site has
to remember it, which is the point; a label built anywhere with a role from
this table gets the inset.
"""

from __future__ import annotations

from clear_budget.ui import label_roles, ui_scale

# (left, top, right, bottom): the order QWidget.setContentsMargins takes.
Inset = tuple[int, int, int, int]

# Page-body label inset. Public because the Recommendations rows align a
# checkbox to their label's first text line and must know where it starts.
# The only inset that scales with the UI, as it always has.
BODY_PADDING_PX = 5
# A line of figures or prose on a page.
_LINE_PX = 5
# The small note under a dialog control.
_NOTE_PX = 2
# The mid-month dip alert's fill.
_ALERT_PX = 8
# The banner's and the Safe to Spend headline's fill.
_FILL_PX = 10
# The status bar's date: a little air above and below, more at the sides.
_STATUS_V_PX = 2
_STATUS_H_PX = 8
# Space under the sign-in heading, before the separator.
_LOGIN_TITLE_BELOW_PX = 4


def _all_sides(px: int) -> Inset:
    return (px, px, px, px)


def _left_right(px: int) -> Inset:
    return (px, 0, px, 0)


def _insets() -> dict[str, Inset]:
    """The table, built on each call so the scaled entry reads the live scale."""
    body = _all_sides(ui_scale.px(BODY_PADDING_PX))
    line = _all_sides(_LINE_PX)
    side = _left_right(_LINE_PX)
    fill = _all_sides(_FILL_PX)
    r = label_roles
    return {
        r.BODY: body,
        r.BODY_DETAIL: body,
        r.HINT: side,
        r.WARN_NOTE: side,
        r.DANGER_NOTE: side,
        r.VALUE: line,
        r.GOOD: line,
        r.WARN: line,
        r.DANGER: line,
        r.NOTE: _all_sides(_NOTE_PX),
        r.LOGIN_TITLE: (0, 0, 0, _LOGIN_TITLE_BELOW_PX),
        r.STATUS_DATE: (_STATUS_H_PX, _STATUS_V_PX, _STATUS_H_PX, _STATUS_V_PX),
        r.SOLVENCY_BANNER: fill,
        r.SAFE_TO_SPEND_HEADLINE: fill,
        r.SOLVENCY_MIDMONTH_ALERT: _all_sides(_ALERT_PX),
        r.SOLVENCY_COMMITTED: line,
        r.SOLVENCY_ASSUMED_NOTE: line,
        r.SOLVENCY_SHORTFALL: line,
        r.SOLVENCY_REMAINING_BANK: line,
        r.SOLVENCY_REMAINING_CARD: line,
        r.SOLVENCY_BREAKDOWN: line,
        r.SOLVENCY_PROJECTION: line,
    }


def inset_for(role: str) -> Inset | None:
    """The inset a label with object name `role` takes; None for no inset."""
    return _insets().get(role)
