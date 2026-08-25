"""The export chart's fixed appearance: its colours and its metrics.

Split from chart_svg so that file holds the drawing and this one holds what
it draws WITH, the same shape the on-screen chart has in ui.theme_tokens and
ui.ui_scale. Names lose the leading underscore they carried while they were
private to one module; the module itself is the private one.

Fixed dark palette, matching the app's dark theme, rather than following
whichever theme is active. An export that changed appearance depending on
what the toggle happened to be set to would be unpredictable and the app's
own identity is the dark one. It carries its own background rather than
relying on the page, so it reads correctly wherever it is embedded. Printing
one will use ink; that is the accepted cost of matching the app.

No Qt and no I/O, so the reporting layer can import it without reaching up
into the UI.
"""

from __future__ import annotations

from clear_budget.shared import palette

# The app's dark palette, mirrored here because the application layer may not
# import ui.theme_tokens. Values match DARK / SERIES_DARK / CURVE_DARK.
PANEL = palette.MUTED_BLUE_18
MUTED = palette.GREY_65
GRID = palette.MUTED_BLUE_28
ZERO_LINE = palette.RED_71
CURVE = palette.FUCHSIA_73
SERIES = (
    palette.MUTED_BLUE_84,
    palette.BLUE_68,
    palette.AMBER_56,
    palette.VIOLET_74,
    palette.PINK_70,
    palette.INDIGO_74,
)

# Role colours for a chart plotting a SINGLE series, mirroring
# CHART_LINE_DARK / CHART_BAR_DARK / SOLO_CURVE_DARK in ui.theme_tokens. With
# one series nothing needs telling apart, so the mark says what it IS: a deep
# blue line for the running balance, lavender bars for the individual days. The
# line stays neutral because it spans positive and negative days alike; a bar
# is one day, so the safe colour states a fact about a day that really is in
# credit. A below-zero bar still fills in ZERO_LINE's red.
SOLO_LINE = palette.CYAN_48
SOLO_BAR = palette.VIOLET_74
SOLO_CURVE = SOLO_LINE
# A day below zero but inside an ARRANGED overdraft, mirroring
# CHART_BAR_WITHIN_DARK. The facility is there to absorb that day, so red
# would say a payment bounced when none did; red stays for a day past the
# agreed floor. With no facility the floor is zero and this never appears.
SOLO_BAR_WITHIN = palette.AMBER_50
# A day in credit that is nonetheless spoken for, mirroring
# CHART_BAR_UNDER_FLOOR_DARK. Blended toward THIS chart's own
# background rather than the app window's, because the export carries
# its own panel; the relationship the colour states, quieter than a
# resting bar and still its own hue, is what has to match, not the hex.
# Deliberately not amber: amber already means "inside the arranged
# overdraft" and one colour cannot carry two verdicts.
SOLO_BAR_UNDER = palette.blend(SOLO_BAR, PANEL, palette.BLEND_DIMMED)

WIDTH = 880
HEIGHT = 380
# The left margin grows to fit the widest y-axis label, mirroring the
# on-screen chart's measured margin, so a large balance never truncates.
# SVG has no font metrics at build time, so the width is estimated from the
# label's character count: a digit in a 12px sans face is a touch over 7px
# wide and the estimate rounds up so a label never overruns its estimate.
MARGIN_LEFT_MIN = 96
AXIS_CHAR_WIDTH = 7.2
AXIS_LABEL_GAP = 8
AXIS_LABEL_INSET = 4
MARGIN_RIGHT = 20
MARGIN_TOP = 16
MARGIN_BOTTOM = 40
LEGEND_HEIGHT = 26

GRID_LINES = 4
BAR_SLOT_FILL = 0.8
RANGE_PAD_FRACTION = 0.05
CURVE_WIDTH = 3
LINE_WIDTH = 2
# Thin and dashed: the floor is a threshold to read a bar against,
# never a quantity of its own.
FLOOR_WIDTH = 1
FLOOR_DASH = "4 4"
LEGEND_SWATCH = 12
LEGEND_GAP = 190
AXIS_FONT = 12
