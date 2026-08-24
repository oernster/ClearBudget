"""Remembered save-file location, PER ACCOUNT: load, save and clear.

The path the user last saved the database to is persisted in the same
app-level `ui_settings.json` the theme uses, so Save can go straight back to
the same file on the next run. Absent, empty or unreadable settings simply
mean "no location yet" and Save falls back to prompting, defaulting to the
app's own data directory.

A remembered location WINS over that default, deliberately: the default only
ever decides where the first save is offered.

KEYED BY ACCOUNT, because one value for the machine was answering the wrong
question. Every account shares this settings file, so the single `save_file`
key held whatever the LAST account to save had chosen, so the next account to
press Save was offered that file. Signed in as one user, the overwrite
confirmation named another user's budget: not a stale default but an offer to
write this account's figures over a file belonging to someone else, which in
the ordinary case (a live budget sits at `budget_<user>.db` in this same
directory) is that account's working budget.

The pre-account `save_file` key is IGNORED rather than migrated. It records a
path without recording whose it was, so adopting it would be guessing; the
guess would land on exactly the cross-account overwrite this rewrite exists to
stop. The cost is one prompt, once per account: the first Save after upgrading
behaves as a first Save, which is what it truthfully is.
"""

from __future__ import annotations

import json
from pathlib import Path

from clear_budget.shared.config import Config

_SETTINGS_FILE_NAME = "ui_settings.json"
# The account-keyed map. The pre-account flat key was `save_file`; a settings
# file may still hold it and is left alone rather than read.
_SAVE_FILES_KEY = "save_files"


def _settings_path() -> Path:
    return Config.app_dir() / _SETTINGS_FILE_NAME


def _all_settings() -> dict:
    try:
        data = json.loads(_settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_save_location(username: str) -> Path | None:
    """Return `username`'s remembered save file; None if none is usable."""
    saved = _all_settings().get(_SAVE_FILES_KEY)
    if not isinstance(saved, dict):
        return None
    value = saved.get(username)
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value)


def store_save_location(username: str, path: Path) -> None:
    """Persist `path` as `username`'s remembered save file, best-effort.

    Shares the settings file with the theme and with every other account, so
    existing keys and other accounts' entries are preserved. A write failure is
    swallowed: the in-session save still happened and the only cost is being
    prompted again next run.
    """
    settings = _settings_path()
    try:
        settings.parent.mkdir(parents=True, exist_ok=True)
        data = _all_settings()
        saved = data.get(_SAVE_FILES_KEY)
        if not isinstance(saved, dict):
            saved = {}
        saved[username] = str(path)
        data[_SAVE_FILES_KEY] = saved
        settings.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass
