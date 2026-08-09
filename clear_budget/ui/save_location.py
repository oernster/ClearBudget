"""Remembered save-file location: load, save and clear.

The path the user last saved the database to is persisted in the same
app-level `ui_settings.json` the theme uses, so Save can go straight back to
the same file on the next run. Absent, empty or unreadable settings simply
mean "no location yet" and Save falls back to prompting, defaulting to the
user's Downloads folder.
"""

from __future__ import annotations

import json
from pathlib import Path

from clear_budget.shared.config import Config

_SETTINGS_FILE_NAME = "ui_settings.json"
_SAVE_FILE_KEY = "save_file"


def _settings_path() -> Path:
    return Config.app_dir() / _SETTINGS_FILE_NAME


def load_save_location() -> Path | None:
    """Return the remembered save file path or None if none is usable."""
    try:
        data = json.loads(_settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get(_SAVE_FILE_KEY) if isinstance(data, dict) else None
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value)


def store_save_location(path: Path) -> None:
    """Persist `path` as the remembered save file, best-effort.

    Shares the settings file with the theme, so existing keys are preserved.
    A write failure is swallowed: the in-session save still happened and the
    only cost is being prompted again next run.
    """
    settings = _settings_path()
    try:
        settings.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data[_SAVE_FILE_KEY] = str(path)
        settings.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass
