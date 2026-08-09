"""Qt-free tests for the remembered save-file location.

Three rules, all directly user-visible:

  * with no location remembered, Save behaves as Save As (load returns None);
  * once a save happens, the same file is offered on every later run;
  * a damaged or hand-edited settings file means "no location yet", never a
    crash and never a made-up path.

The location shares `ui_settings.json` with the theme, so writing one must
never drop the other. Config.app_dir is redirected to a tmp_path throughout,
so these never read or write the real ~/.clearbudget.
"""

import json
from pathlib import Path

import pytest

from clear_budget.shared.config import Config
from clear_budget.ui import save_location

_SETTINGS_NAME = "ui_settings.json"


@pytest.fixture
def app_dir(tmp_path, monkeypatch):
    """Redirect the settings file into a scratch dir for the whole test."""
    monkeypatch.setattr(Config, "app_dir", staticmethod(lambda: tmp_path))
    return tmp_path


def _settings(app_dir):
    return app_dir / _SETTINGS_NAME


def test_a_fresh_install_has_no_remembered_location(app_dir):
    assert not _settings(app_dir).exists()
    assert save_location.load_save_location() is None


def test_a_saved_location_is_remembered_for_the_next_run(app_dir):
    target = Path("C:/Users/someone/Downloads/clearbudget_backup.db")
    save_location.store_save_location(target)
    assert save_location.load_save_location() == target


def test_the_last_save_wins(app_dir):
    save_location.store_save_location(Path("first.db"))
    save_location.store_save_location(Path("second.db"))
    assert save_location.load_save_location() == Path("second.db")


def test_storing_the_location_leaves_other_settings_alone(app_dir):
    """The file is shared with the theme, so a write must not drop it."""
    _settings(app_dir).write_text(json.dumps({"theme": "light"}), encoding="utf-8")
    save_location.store_save_location(Path("backup.db"))
    data = json.loads(_settings(app_dir).read_text(encoding="utf-8"))
    assert data == {"theme": "light", "save_file": "backup.db"}


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not json at all",
        "[]",
        '"backup.db"',
        '{"save_file": null}',
        '{"save_file": 7}',
        '{"save_file": "   "}',
    ],
)
def test_an_unusable_settings_file_means_no_location(app_dir, content):
    _settings(app_dir).write_text(content, encoding="utf-8")
    assert save_location.load_save_location() is None
