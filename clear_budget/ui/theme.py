"""Theme selection: load, apply, toggle and persist the app theme.

The active theme name is held as a dynamic property on the QApplication (no
module-level state) and persisted to an app-level JSON settings file in the
ClearBudget data directory, so the choice applies from the login screen
onward and survives restarts. Applying a theme restyles the whole app at
runtime; the sun/moon toggle buttons in every nav tray are refreshed by
object name so each tab's button always shows the mode a press switches to.
"""

from __future__ import annotations

import json

from clear_budget.shared.config import Config
from clear_budget.ui.theme_qss import build_qss
from clear_budget.ui.theme_tokens import (
    THEME_DARK,
    THEME_LIGHT,
    state_colours_for,
    tokens_for,
)

_SETTINGS_FILE_NAME = "ui_settings.json"
_THEME_KEY = "theme"
_APP_THEME_PROPERTY = "clearbudget_theme"

# The glyph shows the mode a press switches TO, not the current one.
_TOGGLE_GLYPHS = {THEME_DARK: "☀️", THEME_LIGHT: "\U0001f319"}
_TOGGLE_TOOLTIPS = {
    THEME_DARK: "Switch to light mode",
    THEME_LIGHT: "Switch to dark mode",
}


def _settings_path():
    return Config.app_dir() / _SETTINGS_FILE_NAME


def load_saved_theme() -> str:
    """Return the persisted theme name, defaulting to dark."""
    try:
        data = json.loads(_settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return THEME_DARK
    name = data.get(_THEME_KEY) if isinstance(data, dict) else None
    return name if name in (THEME_DARK, THEME_LIGHT) else THEME_DARK


def _save_theme(name: str) -> None:
    path = _settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data[_THEME_KEY] = name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        # Persistence is best-effort; the in-session theme still applies.
        pass


def current_theme(app) -> str:
    """Return the theme the given QApplication is currently showing.

    Tolerates `app` being None so the pure colour rules stay callable without a
    QApplication (the Qt-free solvency-colour tests rely on this), in which
    case the dark default applies.
    """
    if app is None:
        return THEME_DARK
    name = app.property(_APP_THEME_PROPERTY)
    return name if name in (THEME_DARK, THEME_LIGHT) else THEME_DARK


def colours() -> dict[str, str]:
    """Return the active theme's chrome tokens.

    For the handful of places that must resolve a colour in code (a banner
    fill, a traffic-light state) rather than through a QSS role.
    """
    from PySide6.QtWidgets import QApplication

    return tokens_for(current_theme(QApplication.instance()))


def state_colours() -> dict[str, str]:
    """Return the active theme's solvency traffic-light palette."""
    from PySide6.QtWidgets import QApplication

    return state_colours_for(current_theme(QApplication.instance()))


def toggle_glyph(theme_name: str) -> str:
    """Return the sun/moon glyph a toggle button shows under `theme_name`."""
    return _TOGGLE_GLYPHS[theme_name]


def toggle_glyphs() -> tuple[str, ...]:
    """Every glyph a toggle button can show, for sizing one that swaps.

    The button's glyph changes under it, so a size taken from whichever face
    happened to be showing would jump at the next theme switch.
    """
    return tuple(_TOGGLE_GLYPHS.values())


def toggle_tooltip(theme_name: str) -> str:
    """Return the toggle button tooltip under `theme_name`."""
    return _TOGGLE_TOOLTIPS[theme_name]


def apply_theme(app, name: str) -> None:
    """Restyle the whole app to `name`, persist it and refresh the toggles."""
    app.setStyleSheet(build_qss(tokens_for(name), state_colours_for(name)))
    app.setProperty(_APP_THEME_PROPERTY, name)
    _save_theme(name)
    _refresh_toggle_buttons(app, name)
    _restyle_dynamic_views(app)


def toggle_theme(app) -> None:
    """Switch between dark and light at runtime."""
    now = current_theme(app)
    apply_theme(app, THEME_LIGHT if now == THEME_DARK else THEME_DARK)


def _refresh_toggle_buttons(app, name: str) -> None:
    """Point every tray's toggle button at the mode a press switches to.

    Through `apply_toggle_glyph` rather than `setText`, because the sun and the
    moon paint different fractions of their em box: the incoming glyph has to
    be re-sized against the nav icon, not just swapped in at the size the
    outgoing one needed.
    """
    from clear_budget.ui.utils.format_helpers import apply_toggle_glyph

    for widget in app.allWidgets():
        if widget.objectName() == "ThemeToggleButton":
            apply_toggle_glyph(widget, toggle_glyph(name))
            widget.setToolTip(toggle_tooltip(name))


def _restyle_dynamic_views(app) -> None:
    """Ask every view that paints its own colours to rebuild.

    Most widgets follow the theme through the stylesheet alone. Content built
    in code with resolved colours (the card panels, the projection cells, the
    solvency lines, table row colours) cannot, so any widget may expose a
    `restyle()` method and it is called here after the switch.
    """
    for widget in app.allWidgets():
        restyle = getattr(widget, "restyle", None)
        if callable(restyle):
            restyle()
