"""Formatting helpers for UI display, plus the nav-tray re-exports."""

# Re-exported from the application layer, where they sit inside the coverage
# gate. Turning pence into a figure a person reads is not presentation, so it
# does not belong in a module excluded from that gate. They stay importable
# from here so none of the sixty-two call sites had to move.
from clear_budget.application.formatting import fmt, format_category, percentage

# The nav-tray machinery lives in nav_header (extracted whole to keep this
# module clear of the LOC band); the names stay importable from here for the
# same reason as the formatting trio above.
from clear_budget.ui.utils.nav_header import (
    NAV_ICON_BTN_CHROME_PX,
    NAV_LABEL_DEFAULT_COLOR,
    TOGGLE_ICON_SCALE,
    TOGGLE_TARGET_PROPERTY,
    apply_nav_label_color,
    apply_toggle_icon,
    build_centered_nav_header,
    build_nav_month_widget,
    nav_glyph_height,
)

__all__ = [
    "MONTH_NAMES",
    "NAV_ICON_BTN_CHROME_PX",
    "NAV_LABEL_DEFAULT_COLOR",
    "TOGGLE_ICON_SCALE",
    "TOGGLE_TARGET_PROPERTY",
    "apply_nav_label_color",
    "apply_toggle_icon",
    "build_centered_nav_header",
    "build_nav_month_widget",
    "fmt",
    "format_category",
    "nav_glyph_height",
    "percentage",
]

MONTH_NAMES = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
