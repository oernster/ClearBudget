"""Qt-free tests for which theme the app comes up in.

Two rules, both directly user-visible:

  * the first EVER run, with no settings file, comes up dark;
  * every run after that comes up in whatever the last run left.

Dark is also the fallback for a settings file that is empty, corrupt or
hand-edited to something unrecognised, so a damaged file can never silently
flip the app into the other theme.

Config.app_dir is redirected to a tmp_path throughout, so these never read or
write the real ~/.clearbudget.
"""

import json

import pytest

from clear_budget.shared.config import Config
from clear_budget.ui import theme
from clear_budget.ui.theme_tokens import THEME_DARK, THEME_LIGHT

_SETTINGS_NAME = "ui_settings.json"


@pytest.fixture
def app_dir(tmp_path, monkeypatch):
    """Redirect the settings file into a scratch dir for the whole test."""
    monkeypatch.setattr(Config, "app_dir", staticmethod(lambda: tmp_path))
    return tmp_path


def _settings(app_dir):
    return app_dir / _SETTINGS_NAME


def test_the_first_ever_run_comes_up_dark(app_dir):
    """A fresh install has no settings file at all."""
    assert not _settings(app_dir).exists()
    assert theme.load_saved_theme() == THEME_DARK


@pytest.mark.parametrize("left_in", [THEME_DARK, THEME_LIGHT])
def test_a_later_run_comes_up_in_the_mode_it_was_left_in(app_dir, left_in):
    """Whatever the last run saved is what the next run shows."""
    theme._save_theme(left_in)
    assert theme.load_saved_theme() == left_in


def test_the_mode_survives_repeated_switching(app_dir):
    """The last switch wins, not the first one made in the session."""
    theme._save_theme(THEME_LIGHT)
    theme._save_theme(THEME_DARK)
    theme._save_theme(THEME_LIGHT)
    assert theme.load_saved_theme() == THEME_LIGHT


def test_saving_the_theme_leaves_other_settings_alone(app_dir):
    """The file is shared, so a theme write must not drop its neighbours."""
    _settings(app_dir).write_text(json.dumps({"other": 1}), encoding="utf-8")
    theme._save_theme(THEME_LIGHT)
    data = json.loads(_settings(app_dir).read_text(encoding="utf-8"))
    assert data == {"other": 1, "theme": THEME_LIGHT}


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not json at all",
        "[]",
        '"light"',
        '{"theme": "chartreuse"}',
        '{"theme": null}',
    ],
)
def test_an_unusable_settings_file_falls_back_to_dark(app_dir, content):
    """Dark is the fallback everywhere, never light."""
    _settings(app_dir).write_text(content, encoding="utf-8")
    assert theme.load_saved_theme() == THEME_DARK
