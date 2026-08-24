"""Tests for UserStore: authentication and user management."""

import sqlite3

import pytest

from clear_budget.auth.user_store import UserStore


@pytest.fixture()
def store(tmp_path):
    """Fresh in-memory UserStore backed by a temp file."""
    s = UserStore(tmp_path / "users.db")
    yield s
    s.close()


class TestHasUsers:
    """Test UserStore.has_users."""

    def test_empty_store_has_no_users(self, store: UserStore) -> None:
        assert store.has_users() is False

    def test_after_create_has_users(self, store: UserStore) -> None:
        store.create_user("alice", "password1", is_admin=True)
        assert store.has_users() is True


class TestCreateUser:
    """Test UserStore.create_user."""

    def test_create_returns_user_and_recovery_code(self, store: UserStore) -> None:
        user, code = store.create_user("alice", "secret99", is_admin=False)
        assert user.username == "alice"
        assert user.is_admin is False
        assert user.id > 0
        assert len(code) >= 16

    def test_create_admin_user(self, store: UserStore) -> None:
        user, _ = store.create_user("bob", "pass1234", is_admin=True)
        assert user.is_admin is True

    def test_duplicate_username_raises(self, store: UserStore) -> None:
        store.create_user("alice", "pass1234")
        with pytest.raises(sqlite3.IntegrityError):
            store.create_user("alice", "other1234")

    def test_username_case_insensitive_duplicate(self, store: UserStore) -> None:
        store.create_user("Alice", "pass1234")
        with pytest.raises(sqlite3.IntegrityError):
            store.create_user("ALICE", "other1234")

    def test_recovery_codes_are_unique_per_user(self, store: UserStore) -> None:
        _, code1 = store.create_user("alice", "pass1234")
        _, code2 = store.create_user("bob", "pass1234")
        assert code1 != code2


class TestVerifyPassword:
    """Test UserStore.verify_password."""

    def test_correct_credentials_return_user(self, store: UserStore) -> None:
        store.create_user("alice", "correctpass")
        user = store.verify_password("alice", "correctpass")
        assert user is not None
        assert user.username == "alice"

    def test_wrong_password_returns_none(self, store: UserStore) -> None:
        store.create_user("alice", "correctpass")
        result = store.verify_password("alice", "wrongpass")
        assert result is None

    def test_unknown_username_returns_none(self, store: UserStore) -> None:
        result = store.verify_password("nobody", "somepass")
        assert result is None

    def test_case_insensitive_username(self, store: UserStore) -> None:
        store.create_user("Alice", "pass1234")
        user = store.verify_password("ALICE", "pass1234")
        assert user is not None


class TestVerifyRecoveryCode:
    """Test UserStore.verify_recovery_code."""

    def test_correct_code_returns_true(self, store: UserStore) -> None:
        store.create_user("alice", "pass1234")
        _, code = store.create_user("bob", "pass5678")
        assert store.verify_recovery_code("bob", code) is True

    def test_wrong_code_returns_false(self, store: UserStore) -> None:
        store.create_user("alice", "pass1234")
        assert store.verify_recovery_code("alice", "totallyworng") is False

    def test_unknown_user_returns_false(self, store: UserStore) -> None:
        assert store.verify_recovery_code("nobody", "somecode") is False


class TestChangePassword:
    """Test UserStore.change_password."""

    def test_change_password_allows_new_login(self, store: UserStore) -> None:
        store.create_user("alice", "old_pass")
        store.change_password("alice", "new_pass")
        assert store.verify_password("alice", "new_pass") is not None

    def test_old_password_rejected_after_change(self, store: UserStore) -> None:
        store.create_user("alice", "old_pass")
        store.change_password("alice", "new_pass")
        assert store.verify_password("alice", "old_pass") is None


class TestDeleteUser:
    """Test UserStore.delete_user."""

    def test_deleted_user_cannot_login(self, store: UserStore) -> None:
        user, _ = store.create_user("alice", "pass1234")
        store.delete_user(user.id)
        assert store.verify_password("alice", "pass1234") is None

    def test_delete_reduces_user_count(self, store: UserStore) -> None:
        user, _ = store.create_user("alice", "pass1234")
        store.create_user("bob", "pass5678")
        store.delete_user(user.id)
        users = store.get_all_users()
        assert len(users) == 1
        assert users[0].username == "bob"


class TestGetAllUsers:
    """Test UserStore.get_all_users."""

    def test_returns_all_created_users(self, store: UserStore) -> None:
        store.create_user("alice", "pass1234")
        store.create_user("bob", "pass5678")
        users = store.get_all_users()
        names = {u.username for u in users}
        assert "alice" in names
        assert "bob" in names

    def test_empty_store_returns_empty_list(self, store: UserStore) -> None:
        assert store.get_all_users() == []


class TestFindUser:
    """Test UserStore.find_user."""

    def test_find_existing_user(self, store: UserStore) -> None:
        store.create_user("alice", "pass1234")
        user = store.find_user("alice")
        assert user is not None
        assert user.username == "alice"

    def test_find_nonexistent_user_returns_none(self, store: UserStore) -> None:
        assert store.find_user("nobody") is None

    def test_find_case_insensitive(self, store: UserStore) -> None:
        store.create_user("Alice", "pass1234")
        assert store.find_user("ALICE") is not None


class TestHashPasswordAndRecoveryCode:
    """Test UserStore static helpers."""

    def test_hash_password_round_trips(self) -> None:
        import bcrypt

        hashed = UserStore.hash_password("secret99")
        assert bcrypt.checkpw(b"secret99", hashed.encode())

    def test_generate_recovery_code_round_trips(self) -> None:
        import bcrypt

        code, hashed = UserStore.generate_recovery_code()
        assert len(code) >= 16
        assert bcrypt.checkpw(code.encode(), hashed.encode())

    def test_generate_recovery_code_unique(self) -> None:
        code1, _ = UserStore.generate_recovery_code()
        code2, _ = UserStore.generate_recovery_code()
        assert code1 != code2


class TestAnAlreadyInstalledAccountsFile:
    """A users.db written before the viewer feature was removed still opens.

    Live installs carry an `is_read_only` column this code no longer names.
    SQLite keeps it; the column is NOT NULL with a default, so an insert that
    does not mention it still succeeds. Asserted rather than assumed, because
    the alternative is every existing install failing to create an account.
    """

    def test_a_store_with_the_old_column_still_creates_and_reads_users(
        self, tmp_path
    ) -> None:
        path = tmp_path / "users.db"
        legacy = sqlite3.connect(path)
        legacy.execute("""
            CREATE TABLE users (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                username              TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                password_hash         TEXT    NOT NULL,
                recovery_code_hash    TEXT    NOT NULL,
                is_admin              INTEGER NOT NULL DEFAULT 0,
                created_at            TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_read_only          INTEGER NOT NULL DEFAULT 0
            );
        """)
        legacy.commit()
        legacy.close()

        store = UserStore(path)
        try:
            store.create_user("alice", "pass1234")
            assert store.verify_password("alice", "pass1234") is not None
            assert [u.username for u in store.get_all_users()] == ["alice"]
        finally:
            store.close()
