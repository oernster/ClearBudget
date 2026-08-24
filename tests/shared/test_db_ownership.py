"""Who a budget belongs to; who has to prove it.

The hole these pin: every account's budget lives in one flat directory as
`budget_<user>.db`, on which the Load dialog opens. Loading
validated the schema of the chosen file and nothing else, so any signed-in
user could pick another account's budget out of the file list and open it,
an administrator's included.
"""

from __future__ import annotations

import sqlite3

import pytest

from clear_budget.shared.config import Config, _safe_username
from clear_budget.shared.db_ownership import (
    OWNER_SETTING_KEY,
    challenge_required,
    owner_from_filename,
    owner_from_stamp,
    owner_of,
    safe_username,
    stamp_owner,
)

_USERS = ("alice", "mallory")


def _budget(tmp_path, name: str, owner: str | None = None, settings: bool = True):
    """A database file at `name`, optionally stamped and optionally schema-less."""
    path = tmp_path / name
    conn = sqlite3.connect(path)
    if settings:
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
        if owner is not None:
            stamp_owner(conn, owner)
    conn.commit()
    conn.close()
    return path


# --------------------------------------------------------------------------
# The sanitiser this module mirrors.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw", ["alice", "Alice", "MALLORY", "user name", "user.name", "a/b\\c", "ÜBER"]
)
def test_the_mirrored_sanitiser_matches_the_one_that_writes_the_path(raw) -> None:
    """The two must not drift: the file name is a load-time security signal."""
    assert safe_username(raw) == _safe_username(raw)


def test_the_sanitiser_matches_the_name_config_actually_writes(tmp_path) -> None:
    """Belt and braces: assert against a real path, not just the helper."""
    written = Config.for_user("Alice Smith").db_path.name
    assert written == f"budget_{safe_username('Alice Smith')}.db"


# --------------------------------------------------------------------------
# The stamp inside the file.
# --------------------------------------------------------------------------


def test_a_stamped_budget_names_its_owner(tmp_path) -> None:
    assert owner_from_stamp(_budget(tmp_path, "b.db", owner="alice")) == "alice"


def test_an_unstamped_budget_names_nobody(tmp_path) -> None:
    assert owner_from_stamp(_budget(tmp_path, "b.db")) is None


def test_a_file_without_a_settings_table_names_nobody(tmp_path) -> None:
    assert owner_from_stamp(_budget(tmp_path, "b.db", settings=False)) is None


def test_a_file_that_is_not_a_database_names_nobody(tmp_path) -> None:
    rubbish = tmp_path / "notes.db"
    rubbish.write_bytes(b"this is not a database")
    assert owner_from_stamp(rubbish) is None


def test_a_missing_file_names_nobody(tmp_path) -> None:
    assert owner_from_stamp(tmp_path / "gone.db") is None


def test_an_empty_owner_value_names_nobody(tmp_path) -> None:
    """A blank stamp is no stamp, not an account called empty string."""
    path = _budget(tmp_path, "b.db")
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?)", (OWNER_SETTING_KEY, "")
    )
    conn.commit()
    conn.close()
    assert owner_from_stamp(path) is None


def test_a_stamp_is_written_once_and_never_overwritten(tmp_path) -> None:
    """Otherwise opening a file would be a way to CLAIM it."""
    path = _budget(tmp_path, "b.db", owner="alice")
    conn = sqlite3.connect(path)
    stamp_owner(conn, "mallory")
    conn.close()
    assert owner_from_stamp(path) == "alice"


# --------------------------------------------------------------------------
# The file name, which is what covers databases written before the stamp.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, expected",
    [
        ("budget_alice.db", "alice"),
        ("budget_alice__holiday.db", "alice"),
        ("budget_mallory.db", "mallory"),
        ("budget_nobody.db", None),
        ("users.db", None),
        ("clearbudget_backup.db", None),
        ("budget_alice.sqlite", None),
    ],
)
def test_the_file_name_resolves_against_real_accounts(tmp_path, name, expected) -> None:
    assert owner_from_filename(tmp_path / name, _USERS) == expected


def test_the_file_name_is_matched_case_insensitively(tmp_path) -> None:
    """The sanitiser lowercases, so `Alice` writes `budget_alice.db`."""
    assert owner_from_filename(tmp_path / "budget_alice.db", ["Alice"]) == "Alice"


def test_an_ambiguous_file_name_resolves_to_nobody(tmp_path) -> None:
    """The sanitiser is lossy. Guessing would challenge the wrong account and
    lock a file nobody could then open, so an ambiguous name is unowned."""
    assert owner_from_filename(tmp_path / "budget_a_b.db", ["a b", "a.b"]) is None


# --------------------------------------------------------------------------
# The two together.
# --------------------------------------------------------------------------


def test_the_stamp_beats_the_file_name(tmp_path) -> None:
    """Copying a budget to another name must not launder its ownership."""
    path = _budget(tmp_path, "budget_mallory.db", owner="alice")
    assert owner_of(path, _USERS) == "alice"


def test_the_file_name_answers_when_there_is_no_stamp(tmp_path) -> None:
    """Every budget written before stamping existed relies on this."""
    path = _budget(tmp_path, "budget_alice.db")
    assert owner_of(path, _USERS) == "alice"


def test_a_file_answering_neither_belongs_to_nobody(tmp_path) -> None:
    assert owner_of(_budget(tmp_path, "my_backup.db"), _USERS) is None


# --------------------------------------------------------------------------
# The decision the load flow actually asks for.
# --------------------------------------------------------------------------


def test_loading_your_own_budget_asks_nothing(tmp_path) -> None:
    path = _budget(tmp_path, "budget_alice.db", owner="alice")
    assert challenge_required(path, "alice", _USERS) is None


def test_loading_your_own_backup_from_elsewhere_asks_nothing(tmp_path) -> None:
    """An export kept outside the app is the loader's own business."""
    path = _budget(tmp_path, "clearbudget_backup.db")
    assert challenge_required(path, "mallory", _USERS) is None


def test_loading_another_account_challenges_that_account(tmp_path) -> None:
    """The reported hole. The challenge names ALICE, never the loader."""
    path = _budget(tmp_path, "budget_alice.db", owner="alice")
    assert challenge_required(path, "mallory", _USERS) == "alice"


def test_the_challenge_survives_the_file_being_copied_and_renamed(tmp_path) -> None:
    """Copy it out and rename it and the stamp still names its owner."""
    path = _budget(tmp_path, "innocent_looking.db", owner="alice")
    assert challenge_required(path, "mallory", _USERS) == "alice"


def test_an_unstamped_budget_of_anothers_is_still_challenged(tmp_path) -> None:
    """The case every pre-existing database falls into."""
    path = _budget(tmp_path, "budget_alice.db")
    assert challenge_required(path, "mallory", _USERS) == "alice"
