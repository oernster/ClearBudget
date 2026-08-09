"""Qt-free tests for the skipped-update persistence.

The skip lives in the same ui_settings.json as the theme, so saving one must
never disturb the other. Config.app_dir is redirected to a tmp_path
throughout, so these never read or write the real ~/.clearbudget.
"""

import json

import pytest

from clear_budget.shared.config import Config
from clear_budget.ui import update_check

_SETTINGS_NAME = "ui_settings.json"


@pytest.fixture
def app_dir(tmp_path, monkeypatch):
    """Redirect the settings file into a scratch dir for the whole test."""
    monkeypatch.setattr(Config, "app_dir", staticmethod(lambda: tmp_path))
    return tmp_path


def _settings(app_dir):
    return app_dir / _SETTINGS_NAME


def test_a_fresh_install_has_no_skipped_version(app_dir):
    assert not _settings(app_dir).exists()
    assert update_check.load_skipped_version() is None


def test_a_saved_skip_is_loaded_back(app_dir):
    update_check.save_skipped_version("4.3.0")
    assert update_check.load_skipped_version() == "4.3.0"


def test_saving_a_skip_preserves_the_other_settings(app_dir):
    _settings(app_dir).write_text(json.dumps({"theme": "light"}), encoding="utf-8")
    update_check.save_skipped_version("4.3.0")
    data = json.loads(_settings(app_dir).read_text(encoding="utf-8"))
    assert data["theme"] == "light"
    assert data["skipped_update"] == "4.3.0"


@pytest.mark.parametrize("content", ["", "not json", json.dumps(["a", "list"])])
def test_a_damaged_settings_file_reads_as_no_skip(app_dir, content):
    _settings(app_dir).write_text(content, encoding="utf-8")
    assert update_check.load_skipped_version() is None


@pytest.mark.parametrize("content", ["not json", json.dumps(["a", "list"])])
def test_saving_over_a_damaged_file_recovers_it(app_dir, content):
    _settings(app_dir).write_text(content, encoding="utf-8")
    update_check.save_skipped_version("4.3.0")
    assert update_check.load_skipped_version() == "4.3.0"


@pytest.mark.parametrize("value", [7, "", None])
def test_a_non_version_skip_value_reads_as_no_skip(app_dir, value):
    _settings(app_dir).write_text(
        json.dumps({"skipped_update": value}), encoding="utf-8"
    )
    assert update_check.load_skipped_version() is None
