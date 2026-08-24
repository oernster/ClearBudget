"""UserStore - manages the central users authentication database.

Passwords are hashed with bcrypt (Blowfish-based).  A one-time recovery code
is generated at account creation, shown to the user exactly once and stored
as a bcrypt hash.  It can be used to reset a forgotten password.

A username must also be distinct in its FILESYSTEM form, not just as typed.
Every account's budget lives at `budget_<safe username>.db` and its budget
list at `budgets_<safe username>.json`, where the safe form maps anything
outside `[A-Za-z0-9_-]` to an underscore. That mapping is lossy, so
"john doe" and "john_doe" are two accounts resolving to ONE file: measured,
both opened `budget_john_doe.db`, which means shared bills, shared income,
shared balance and either account able to delete the other's data. The
database's own UNIQUE constraint cannot see this, because as typed the two
names are different.

So the collision is refused where the account is created, which is the only
place it can enter. Renaming an account is not offered, so there is no second
door.
"""

import secrets
import sqlite3
from pathlib import Path

import bcrypt

from clear_budget.auth.models import User
from clear_budget.shared.db_ownership import safe_username

# bcrypt work factor - 12 is a solid default (≈0.3 s on modern hardware).
_BCRYPT_ROUNDS = 12

# Recovery code: 20 url-safe characters
_RECOVERY_CODE_BYTES = 15  # 15 bytes → 20 base64url chars


class UsernameCollisionError(ValueError):
    """A username that would share another account's files."""


class UserStore:
    """CRUD and authentication for user accounts."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                username              TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                password_hash         TEXT    NOT NULL,
                recovery_code_hash    TEXT    NOT NULL,
                is_admin              INTEGER NOT NULL DEFAULT 0,
                created_at            TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def has_users(self) -> bool:
        """Return True if at least one user account exists."""
        row = self._conn.execute("SELECT COUNT(*) FROM users").fetchone()
        return row[0] > 0

    def get_all_users(self) -> list[User]:
        rows = self._conn.execute(
            "SELECT id, username, is_admin FROM users ORDER BY id"
        ).fetchall()
        return [
            User(
                id=r["id"],
                username=r["username"],
                is_admin=bool(r["is_admin"]),
            )
            for r in rows
        ]

    def find_user(self, username: str) -> User | None:
        row = self._conn.execute(
            "SELECT id, username, is_admin FROM users"
            " WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
        if row is None:
            return None
        return User(
            id=row["id"],
            username=row["username"],
            is_admin=bool(row["is_admin"]),
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def verify_password(self, username: str, password: str) -> User | None:
        """Return User if credentials are valid, else None."""
        row = self._conn.execute(
            "SELECT id, username, password_hash, is_admin FROM users"
            " WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
        if row is None:
            return None
        if bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            return User(
                id=row["id"],
                username=row["username"],
                is_admin=bool(row["is_admin"]),
            )
        return None

    def verify_recovery_code(self, username: str, code: str) -> bool:
        """Return True if the recovery code matches for username."""
        row = self._conn.execute(
            "SELECT recovery_code_hash FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
        if row is None:
            return False
        hashed = row["recovery_code_hash"].encode()
        return bcrypt.checkpw(code.strip().encode(), hashed)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """Return a bcrypt hash of password."""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(_BCRYPT_ROUNDS)).decode()

    @staticmethod
    def generate_recovery_code() -> tuple[str, str]:
        """Return (plaintext_recovery_code, bcrypt_hash)."""
        recovery_code = secrets.token_urlsafe(_RECOVERY_CODE_BYTES)
        recovery_hash = UserStore.hash_password(recovery_code)
        return recovery_code, recovery_hash

    def colliding_account(self, username: str) -> str | None:
        """An existing account whose FILES `username` would share; else None.

        Compared in the safe form the path builder uses, so it catches the
        pair the `UNIQUE` constraint cannot: two names that differ as typed
        and land on one budget file.
        """
        wanted = safe_username(username)
        for user in self.get_all_users():
            # A name differing only in CASE is the same account by this
            # store's own rule (`UNIQUE COLLATE NOCASE`), so it is left to
            # that constraint, which refuses it in the words the user needs:
            # already taken, rather than too close to something else.
            if user.username.casefold() == username.casefold():
                continue
            if safe_username(user.username) == wanted:
                return user.username
        return None

    def create_user(
        self, username: str, password: str, is_admin: bool = False
    ) -> tuple["User", str]:
        """Create a new user.  Returns (User, plaintext_recovery_code).

        The recovery code is shown to the user exactly once and stored hashed.

        Raises `UsernameCollisionError` when the name would share an existing
        account's budget file (see the module docstring). Refused here rather
        than in the dialog, so no caller can create such a pair.
        """
        clash = self.colliding_account(username)
        if clash is not None:
            raise UsernameCollisionError(
                f"'{username}' is too close to the existing account "
                f"'{clash}'. The two would share one budget file, so each "
                "would see and be able to delete the other's figures. Choose "
                "a name that differs by more than punctuation or spacing."
            )
        password_hash = self.hash_password(password)
        recovery_code, recovery_hash = self.generate_recovery_code()

        cursor = self._conn.execute(
            "INSERT INTO users"
            " (username, password_hash, recovery_code_hash, is_admin)"
            " VALUES (?, ?, ?, ?)",
            (username, password_hash, recovery_hash, int(is_admin)),
        )
        self._conn.commit()
        user = User(id=cursor.lastrowid, username=username, is_admin=is_admin)
        return user, recovery_code

    def change_password(self, username: str, new_password: str) -> None:
        """Replace password hash for username."""
        new_hash = bcrypt.hashpw(
            new_password.encode(), bcrypt.gensalt(_BCRYPT_ROUNDS)
        ).decode()
        self._conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ? COLLATE NOCASE",
            (new_hash, username),
        )
        self._conn.commit()

    def delete_user(self, user_id: int) -> None:
        self._conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
