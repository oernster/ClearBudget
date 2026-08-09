"""Tests for RememberedLogin - remember/recall/forget with a fake keychain."""

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


class TestRememberAndRecall:
    def test_round_trip(self, store: RememberedLogin) -> None:
        store.remember("alice", "hunter2")
        assert store.recall() == ("alice", "hunter2")

    def test_recall_with_nothing_remembered(self, store: RememberedLogin) -> None:
        assert store.recall() is None

    def test_remember_overwrites_previous_user(self, store: RememberedLogin) -> None:
        store.remember("alice", "hunter2")
        store.remember("bob", "swordfish")
        assert store.recall() == ("bob", "swordfish")

    def test_password_never_written_to_disk(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        store.remember("alice", "hunter2")
        sidecar = (tmp_path / _STATE_FILE).read_text(encoding="utf-8")
        assert "hunter2" not in sidecar
        assert json.loads(sidecar) == {"username": "alice"}

    def test_remember_creates_missing_state_dir(
        self, tmp_path: Path, keychain: FakeKeychain
    ) -> None:
        nested = tmp_path / "not-yet-created"
        store = RememberedLogin(nested, backend=keychain)
        store.remember("alice", "hunter2")
        assert store.recall() == ("alice", "hunter2")


class TestForget:
    def test_forget_removes_keychain_entry_and_sidecar(
        self, tmp_path: Path, store: RememberedLogin, keychain: FakeKeychain
    ) -> None:
        store.remember("alice", "hunter2")
        store.forget()
        assert store.recall() is None
        assert keychain.entries == {}
        assert not (tmp_path / _STATE_FILE).exists()

    def test_forget_with_nothing_remembered_is_a_no_op(
        self, store: RememberedLogin
    ) -> None:
        store.forget()
        assert store.recall() is None

    def test_forget_still_removes_sidecar_when_keychain_fails(
        self, tmp_path: Path, store: RememberedLogin, keychain: FakeKeychain
    ) -> None:
        store.remember("alice", "hunter2")
        keychain.fail_delete = True
        store.forget()
        assert not (tmp_path / _STATE_FILE).exists()
        assert store.recall() is None


class TestKeychainFailure:
    def test_remember_leaves_no_sidecar_when_store_fails(
        self, tmp_path: Path, store: RememberedLogin, keychain: FakeKeychain
    ) -> None:
        keychain.fail_set = True
        store.remember("alice", "hunter2")
        assert not (tmp_path / _STATE_FILE).exists()
        assert store.recall() is None

    def test_recall_degrades_when_keychain_fails(
        self, store: RememberedLogin, keychain: FakeKeychain
    ) -> None:
        store.remember("alice", "hunter2")
        keychain.fail_get = True
        assert store.recall() is None

    def test_recall_none_when_keychain_entry_missing(
        self, store: RememberedLogin, keychain: FakeKeychain
    ) -> None:
        store.remember("alice", "hunter2")
        keychain.entries.clear()
        assert store.recall() is None


class TestSidecarCorruption:
    def test_recall_none_on_unreadable_json(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text("not json", encoding="utf-8")
        assert store.recall() is None

    def test_recall_none_when_json_is_not_a_dict(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text('["alice"]', encoding="utf-8")
        assert store.recall() is None

    def test_recall_none_when_username_missing(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text("{}", encoding="utf-8")
        assert store.recall() is None

    def test_recall_none_when_username_blank(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text('{"username": ""}', encoding="utf-8")
        assert store.recall() is None

    def test_recall_none_when_username_not_a_string(
        self, tmp_path: Path, store: RememberedLogin
    ) -> None:
        (tmp_path / _STATE_FILE).write_text('{"username": 7}', encoding="utf-8")
        assert store.recall() is None


class TestDefaultBackend:
    def test_default_backend_is_the_keyring_module(self, tmp_path: Path) -> None:
        keyring = pytest.importorskip("keyring")
        store = RememberedLogin(tmp_path)
        assert store._backend is keyring

    def test_default_backend_function(self) -> None:
        keyring = pytest.importorskip("keyring")
        assert module._default_backend() is keyring
