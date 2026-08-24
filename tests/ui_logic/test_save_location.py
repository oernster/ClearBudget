"""Qt-free tests for the remembered save-file location.

Four rules, all directly user-visible:

  * with no location remembered, Save behaves as Save As (load returns None);
  * once a save happens, the same file is offered on every later run;
  * the answer is PER ACCOUNT, so one account's Save can never be pointed at
    another account's file by the settings alone;
  * a damaged or hand-edited settings file means "no location yet", never a
    crash and never a made-up path.

The third one is why this file changed shape. The location used to be a single
`save_file` key for the machine, so it held whatever the last account to save
had chosen and the next account to press Save was offered that: signed in as
one user, the overwrite confirmation named another user's budget, which in the
ordinary case is that account's live working file.

The location shares `ui_settings.json` with the theme, so writing one must
never drop the other; one account's write must never drop another's.
Config.app_dir is redirected to a tmp_path throughout, so these never read or
write the real data directory.
"""

import json
from pathlib import Path

import pytest

from clear_budget.shared.config import Config
from clear_budget.ui import save_location

_SETTINGS_NAME = "ui_settings.json"
_ALICE = "alice"
_BOB = "bob"


@pytest.fixture
def app_dir(tmp_path, monkeypatch):
    """Redirect the settings file into a scratch dir for the whole test."""
    monkeypatch.setattr(Config, "app_dir", staticmethod(lambda: tmp_path))
    return tmp_path


def _settings(app_dir):
    return app_dir / _SETTINGS_NAME


def test_a_fresh_install_has_no_remembered_location(app_dir):
    assert not _settings(app_dir).exists()
    assert save_location.load_save_location(_ALICE) is None


def test_a_saved_location_is_remembered_for_the_next_run(app_dir):
    target = Path("C:/Users/someone/Downloads/clearbudget_backup_alice.db")
    save_location.store_save_location(_ALICE, target)
    assert save_location.load_save_location(_ALICE) == target


def test_the_last_save_wins_for_that_account(app_dir):
    save_location.store_save_location(_ALICE, Path("first.db"))
    save_location.store_save_location(_ALICE, Path("second.db"))
    assert save_location.load_save_location(_ALICE) == Path("second.db")


class TestOneAccountNeverAnswersForAnother:
    """The defect this shape exists to make impossible."""

    def test_an_account_that_has_never_saved_is_offered_nothing(self, app_dir):
        save_location.store_save_location(_ALICE, Path("alice_backup.db"))
        assert save_location.load_save_location(_BOB) is None

    def test_each_account_keeps_its_own_answer(self, app_dir):
        save_location.store_save_location(_ALICE, Path("alice_backup.db"))
        save_location.store_save_location(_BOB, Path("bob_backup.db"))
        assert save_location.load_save_location(_ALICE) == Path("alice_backup.db")
        assert save_location.load_save_location(_BOB) == Path("bob_backup.db")

    def test_the_pre_account_key_is_ignored_rather_than_adopted(self, app_dir):
        """It records a path without recording whose it was.

        Adopting it would be a guess landing on exactly the
        cross-account overwrite this shape exists to stop.
        """
        _settings(app_dir).write_text(
            json.dumps({"save_file": "someone_elses_budget.db"}), encoding="utf-8"
        )
        assert save_location.load_save_location(_ALICE) is None


def test_storing_the_location_leaves_other_settings_alone(app_dir):
    """The file is shared with the theme, so a write must not drop it."""
    _settings(app_dir).write_text(json.dumps({"theme": "light"}), encoding="utf-8")
    save_location.store_save_location(_ALICE, Path("backup.db"))
    data = json.loads(_settings(app_dir).read_text(encoding="utf-8"))
    assert data == {"theme": "light", "save_files": {_ALICE: "backup.db"}}


def test_storing_one_account_leaves_the_others_alone(app_dir):
    save_location.store_save_location(_BOB, Path("bob_backup.db"))
    save_location.store_save_location(_ALICE, Path("alice_backup.db"))
    data = json.loads(_settings(app_dir).read_text(encoding="utf-8"))
    assert data["save_files"] == {
        _BOB: "bob_backup.db",
        _ALICE: "alice_backup.db",
    }


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not json at all",
        "[]",
        '"backup.db"',
        '{"save_files": null}',
        '{"save_files": 7}',
        '{"save_files": "backup.db"}',
        '{"save_files": {"alice": null}}',
        '{"save_files": {"alice": 7}}',
        '{"save_files": {"alice": "   "}}',
    ],
)
def test_an_unusable_settings_file_means_no_location(app_dir, content):
    _settings(app_dir).write_text(content, encoding="utf-8")
    assert save_location.load_save_location(_ALICE) is None


def test_an_unwritable_settings_file_is_survived(app_dir, monkeypatch):
    """The save itself happened; being prompted again is the whole cost."""

    def refuse(*_args, **_kwargs):
        raise OSError("read-only")

    monkeypatch.setattr(Path, "write_text", refuse)
    save_location.store_save_location(_ALICE, Path("backup.db"))
    assert save_location.load_save_location(_ALICE) is None
