"""Semantic colour tokens for the two application themes.

Every colour the stylesheet builders (theme_qss / _theme_controls) and the
theme-aware inline styles use is named here once per theme. The keys are
semantic (what the colour is FOR), so the light theme is a second dict, not a
second stylesheet. Ring colours follow the app-wide three-state model: no
ring at rest, the green ring token on hover/focus while enabled, the danger
token permanently while disabled.
"""

from __future__ import annotations

THEME_DARK = "dark"
THEME_LIGHT = "light"

DARK: dict[str, str] = {
    "window_bg": "#0a0a0d",
    "panel_bg": "#242938",
    "panel_alt_bg": "#2d3344",
    "inset_bg": "#06070c",
    "calendar_nav_bg": "#1a1f2e",
    "border": "#3a4156",
    "separator": "#1e3a5f",
    "selection_bg": "#1e3a5f",
    "text": "#e5e7eb",
    "text_muted": "#9ca3af",
    "text_disabled": "#6b7280",
    "checkbox_hover": "#d1d5db",
    "accent": "#2dd4bf",
    "info": "#00d4ff",
    "ring": "#34d399",
    "danger": "#f87171",
    "warn": "#fbbf24",
    "primary_bg": "#3b5bdb",
    "primary_hover": "#4a68d6",
    "primary_pressed": "#2f4bb8",
    "primary_text": "#ffffff",
    "danger_btn_bg": "#7a1f25",
    "danger_btn_hover": "#6a1b21",
    "disabled_fill": "#3a4156",
    "scroll_handle": "#9aa3c2",
    "scroll_handle_hover": "#c4cae0",
    "calendar_sel_text": "#0b0f17",
    "input_bg": "#0d1b2a",
    "input_text": "#e2e8f0",
    "link": "#60a5fa",
    "link_hover": "#93c5fd",
    "text_subtle": "#94a3b8",
    "warn_strong": "#f59e0b",
    "danger_strong": "#dc2626",
    "hover_fill": "#1a1a2e",
    "pill_up_bg": "#1e3a8a",
    "pill_down_bg": "#78350f",
    "card_stat_bg": "#1f2937",
    "cell_tight_bg": "#7f1d1d",
    "cell_watch_bg": "#f59e0b",
    "cell_ample_bg": "#14532d",
    "cell_tight_fg": "#ffffff",
    "cell_watch_fg": "#1a1a1a",
    "cell_ample_fg": "#ffffff",
    "bar_text": "#ffffff",
}

LIGHT: dict[str, str] = {
    "window_bg": "#f3f4f6",
    "panel_bg": "#ffffff",
    "panel_alt_bg": "#e5e7eb",
    "inset_bg": "#e5e7eb",
    "calendar_nav_bg": "#e2e8f0",
    "border": "#cbd5e1",
    "separator": "#cbd5e1",
    "selection_bg": "#bfdbfe",
    "text": "#111827",
    "text_muted": "#6b7280",
    "text_disabled": "#9ca3af",
    "checkbox_hover": "#475569",
    "accent": "#0d9488",
    "info": "#0369a1",
    "ring": "#059669",
    "danger": "#dc2626",
    "warn": "#b45309",
    "primary_bg": "#3b5bdb",
    "primary_hover": "#4a68d6",
    "primary_pressed": "#2f4bb8",
    "primary_text": "#ffffff",
    "danger_btn_bg": "#dc2626",
    "danger_btn_hover": "#b91c1c",
    "disabled_fill": "#d1d5db",
    "scroll_handle": "#94a3b8",
    "scroll_handle_hover": "#64748b",
    "calendar_sel_text": "#ffffff",
    "input_bg": "#ffffff",
    "input_text": "#111827",
    "link": "#2563eb",
    "link_hover": "#1d4ed8",
    "text_subtle": "#4b5563",
    "warn_strong": "#b45309",
    "danger_strong": "#b91c1c",
    "hover_fill": "#e5e7eb",
    "pill_up_bg": "#1d4ed8",
    "pill_down_bg": "#b45309",
    "card_stat_bg": "#eef2f7",
    "cell_tight_bg": "#fee2e2",
    "cell_watch_bg": "#fef3c7",
    "cell_ample_bg": "#dcfce7",
    "cell_tight_fg": "#7f1d1d",
    "cell_watch_fg": "#78350f",
    "cell_ample_fg": "#14532d",
    "bar_text": "#111827",
}

# Chart series colours are DATA encodings, not chrome, so they are a separate
# per-theme palette: pastels read on a near-black canvas, saturated mid-tones
# read on a light one. Same hue order in both, so a series keeps its identity
# across a theme switch.
SERIES_DARK = (
    "#34d399",
    "#60a5fa",
    "#fbbf24",
    "#a78bfa",
    "#f472b6",
    "#2dd4bf",
    "#f87171",
    "#fb923c",
)

SERIES_LIGHT = (
    "#059669",
    "#2563eb",
    "#d97706",
    "#7c3aed",
    "#db2777",
    "#0d9488",
    "#dc2626",
    "#ea580c",
)

# Solvency traffic-light states. Like the series palette these are data
# colours, used both as a banner fill and as text on the window background, so
# each theme needs its own set to stay legible in the text role.
STATE_RED = "red"
STATE_AT_RISK = "at_risk"
STATE_CAUTION = "caution"
STATE_SAFE = "safe"

STATES_DARK = {
    STATE_RED: "#f87171",
    STATE_AT_RISK: "#f59e0b",
    STATE_CAUTION: "#fbbf24",
    STATE_SAFE: "#34d399",
}

STATES_LIGHT = {
    STATE_RED: "#dc2626",
    STATE_AT_RISK: "#c2410c",
    STATE_CAUTION: "#b45309",
    STATE_SAFE: "#059669",
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


def state_colours_for(theme_name: str) -> dict[str, str]:
    """Return the solvency state palette for `theme_name`, defaulting to dark."""
    return _STATES_BY_THEME.get(theme_name, STATES_DARK)
