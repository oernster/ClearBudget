"""Tests for RememberedLogin - per-account remember/recall/forget.

Driven through a hand-written fake keychain rather than a mock library, so
what a failing credential store does is stated in the fake and asserted here
rather than arranged per test.

Two properties matter more than the rest and are covered hardest. A password
must never reach the filesystem; every keychain failure must degrade to
"nothing remembered", because sign-in has to work on a machine whose
credential store is locked, absent or refused.
"""

import json
from pathlib import Path

import pytest

from clear_budget.auth import remembered_login as module
from clear_budget.auth.remembered_login import RememberedLogin

_STATE_FILE = "remembered_login.json"


class FakeKeychain:
    """Hand-written in-memory stand-in for the keyring module."""

    def __init__(self) -> None:
        self.entries: dict[tuple[str, str], str] = {}
        self.fail_set = False
        self.fail_get = False
        self.fail_delete = False

    def set_password(self, service: str, username: str, password: str) -> None:
        if self.fail_set:
            raise RuntimeError("keychain unavailable")
        self.entries[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        if self.fail_get:
            raise RuntimeError("keychain unavailable")
        return self.entries.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        if self.fail_delete:
            raise RuntimeError("keychain unavailable")
        del self.entries[(service, username)]


@pytest.fixture()
def keychain() -> FakeKeychain:
    return FakeKeychain()


@pytest.fixture()
def store(tmp_path: Path, keychain: FakeKeychain) -> RememberedLogin:
    return RememberedLogin(tmp_path, backend=keychain)


class TestRememberingSeveralAccounts:
    def test_nothing_is_remembered_to_begin_with(self, store: RememberedLogin) -> None:
        assert store.usernames() == ()
        assert store.last_username() is None

    def test_each_account_is_remembered_separately(
        self, store: RememberedLogin
    ) -> None:
        """The whole point: one machine, several people, one list."""
        store.remember_password("alice", "hunter2")
        store.remember_password("bob", "swordfish")
        assert store.usernames() == ("alice", "bob")
        assert store.recall_password("alice") == "hunter2"
        assert store.recall_password("bob") == "swordfish"

    def test_remembering_the_same_account_twice_updates_it(
        self, store: RememberedLogin
    ) -> None:
        """A changed password replaces the old one rather than adding a row."""
        store.remember_password("alice", "hunter2")
        store.remember_password("alice", "hunter3")
        assert store.usernames() == ("alice",)
        assert store.recall_password("alice") == "hunter3"

    def test_a_username_can_be_remembered_without_a_password(
        self, store: RememberedLogin
    ) -> None:
        """What the account-creation checkbox writes."""
        store.remember_username("alice")
        assert store.usernames() == ("alice",)
        assert store.keeps_password("alice") is False
        assert store.recall_password("alice") is None

    def test_remembering_a_username_leaves_a_kept_password_alone(
        self, store: RememberedLogin
    ) -> None:
        """Remembering the name again must not silently drop the password."""
        store.remember_password("alice", "hunter2")
        store.remember_username("alice")
        assert store.recall_password("alice") == "hunter2"

    def test_a_password_is_only_recalled_for_the_account_that_kept_one(
        self, store: RememberedLogin
    ) -> None:
        store.remember_password("alice", "hunter2")
        store.remember_username("bob")
        assert store.recall_password("bob") is None

    def test_an_unremembered_account_recalls_nothing(
        self, store: RememberedLogin
    ) -> None:
        assert store.recall_password("nobody") is None


class TestTheMostRecentSignIn:
    def test_the_last_sign_in_is_recorded(self, store: RememberedLogin) -> None:
        store.remember_password("alice", "hunter2")
        store.remember_password("bob", "swordfish")
        store.note_signed_in("alice")
        assert store.last_username() == "alice"

    def test_an_unremembered_account_is_not_recorded(
        self, store: RememberedLogin
    ) -> None:
        """Preselecting it would admit to a name the screen does not list."""
        store.remember_password("alice", "hunter2")
        store.note_signed_in("carol")
        assert store.last_username() is None
        assert "carol" not in store.usernames()

    def test_forgetting_the_last_account_clears_it(
        self, store: RememberedLogin
    ) -> None:
        store.remember_password("alice", "hunter2")
        store.note_signed_in("alice")
        store.forget("alice")
        assert store.last_username() is None


class TestForgetting:
    def test_forgetting_removes_the_account_and_its_password(
        self, store: RememberedLogin, keychain: FakeKeychain
    ) -> None:
        store.remember_password("alice", "hunter2")
        store.forget("alice")
        assert store.usernames() == ()
        assert keychain.entries == {}

    def test_forgetting_one_account_leaves_the_others(
        self, store: RememberedLogin
    ) -> None:
        store.remember_password("alice", "hunter2")
        store.remember_password("bob", "swordfish")
        store.forget("alice")
        assert store.usernames() == ("bob",)
        assert store.recall_password("bob") == "swordfish"

    def test_forgetting_only_the_password_keeps_the_username(
        self, store: RememberedLogin, keychain: FakeKeychain
    ) -> None:
        """Unticking the password box must not delist the account."""
        store.remember_password("alice", "hunter2")
        store.forget_password("alice")
        assert store.usernames() == ("alice",)
        assert store.keeps_password("alice") is False
        assert keychain.entries == {}

    def test_forgetting_an_unremembered_account_is_a_no_op(
        self, store: RememberedLogin
    ) -> None:
        store.forget("nobody")
        assert store.usernames() == ()

    def test_forgetting_still_delists_when_the_keychain_fails(
        self, store: RememberedLogin, keychain: FakeKeychain
    ) -> None:
        """An unreachable keychain must not strand a name on the screen."""
        store.remember_password("alice", "hunter2")
        keychain.fail_delete = True
        store.forget("alice")
        assert store.usernames() == ()


class TestThePasswordNeverReachesDisk:
    def test_password_never_written_to_disk(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        store.remember_password("alice", "hunter2")
        assert "hunter2" not in (tmp_path / _STATE_FILE).read_text(encoding="utf-8")

    def test_only_the_name_and_the_flag_are_written(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        store.remember_password("alice", "hunter2")
        data = json.loads((tmp_path / _STATE_FILE).read_text(encoding="utf-8"))
        assert data["accounts"] == [{"username": "alice", "keep_password": True}]

    def test_remember_creates_a_missing_state_dir(
        self, tmp_path: Path, keychain: FakeKeychain
    ) -> None:
        nested = tmp_path / "does" / "not" / "exist"
        store = RememberedLogin(nested, backend=keychain)
        store.remember_password("alice", "hunter2")
        assert store.recall_password("alice") == "hunter2"


class TestAnUnavailableKeychain:
    def test_a_failed_store_remembers_nothing(
        self, tmp_path: Path, store: RememberedLogin, keychain: FakeKeychain
    ) -> None:
        """No half state: a name promising a password it cannot produce."""
        keychain.fail_set = True
        store.remember_password("alice", "hunter2")
        assert store.usernames() == ()
        assert not (tmp_path / _STATE_FILE).exists()

    def test_a_failed_read_recalls_nothing(
        self, store: RememberedLogin, keychain: FakeKeychain
    ) -> None:
        store.remember_password("alice", "hunter2")
        keychain.fail_get = True
        assert store.recall_password("alice") is None

    def test_a_missing_entry_recalls_nothing(
        self, store: RememberedLogin, keychain: FakeKeychain
    ) -> None:
        store.remember_password("alice", "hunter2")
        keychain.entries.clear()
        assert store.recall_password("alice") is None


class TestTheEarlierSingleAccountFile:
    """Every machine the app has already run on carries the older shape."""

    def test_the_old_file_is_read_as_one_remembered_account(
        self, tmp_path: Path, store: RememberedLogin, keychain: FakeKeychain
    ) -> None:
        (tmp_path / _STATE_FILE).write_text('{"username": "alice"}', encoding="utf-8")
        keychain.entries[("ClearBudget", "alice")] = "hunter2"
        assert store.usernames() == ("alice",)
        assert store.last_username() == "alice"
        # The old tick covered both, so that account kept its password.
        assert store.recall_password("alice") == "hunter2"

    def test_a_second_account_joins_the_migrated_one(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text('{"username": "alice"}', encoding="utf-8")
        store.remember_password("bob", "swordfish")
        assert store.usernames() == ("alice", "bob")


class TestSidecarCorruption:
    def test_unreadable_json_remembers_nothing(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text("not json", encoding="utf-8")
        assert store.usernames() == ()

    def test_json_that_is_not_an_object_remembers_nothing(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text('["alice"]', encoding="utf-8")
        assert store.usernames() == ()

    def test_an_object_with_neither_shape_remembers_nothing(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text("{}", encoding="utf-8")
        assert store.usernames() == ()

    def test_a_blank_legacy_username_remembers_nothing(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text('{"username": ""}', encoding="utf-8")
        assert store.usernames() == ()

    def test_a_legacy_username_that_is_not_a_string_remembers_nothing(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text('{"username": 7}', encoding="utf-8")
        assert store.usernames() == ()

    def test_a_null_account_list_remembers_nothing(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text('{"accounts": null}', encoding="utf-8")
        assert store.usernames() == ()

    def test_entries_that_are_not_objects_are_skipped(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text(
            '{"accounts": ["alice", {"username": "bob"}]}', encoding="utf-8"
        )
        assert store.usernames() == ("bob",)

    def test_entries_without_a_usable_username_are_skipped(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text(
            '{"accounts": [{"username": ""}, {"username": 7}, {"keep": 1}]}',
            encoding="utf-8",
        )
        assert store.usernames() == ()

    def test_a_last_that_is_not_a_usable_string_is_ignored(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text(
            '{"accounts": [{"username": "alice"}], "last": 7}', encoding="utf-8"
        )
        assert store.last_username() is None

    def test_a_last_naming_an_unlisted_account_is_ignored(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text(
            '{"accounts": [{"username": "alice"}], "last": "ghost"}',
            encoding="utf-8",
        )
        assert store.last_username() is None


class TestDefaultBackend:
    def test_default_backend_is_the_keyring_module(self, tmp_path: Path) -> None:
        keyring = pytest.importorskip("keyring")
        store = RememberedLogin(tmp_path)
        assert store._backend is keyring

    def test_default_backend_function(self) -> None:
        keyring = pytest.importorskip("keyring")
        assert module._default_backend() is keyring
