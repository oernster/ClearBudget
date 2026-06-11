"""UserStore - manages the central users authentication database.

Passwords are hashed with bcrypt (Blowfish-based).  A one-time recovery code
is generated at account creation, shown to the user exactly once, and stored
as a bcrypt hash.  It can be used to reset a forgotten password.
"""

import secrets
import sqlite3
from pathlib import Path
from typing import Optional

import bcrypt

from clear_budget.auth.models import User

# bcrypt work factor - 12 is a solid default (≈0.3 s on modern hardware).
_BCRYPT_ROUNDS = 12

# Recovery code: 20 url-safe characters
_RECOVERY_CODE_BYTES = 15  # 15 bytes → 20 base64url chars


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
        try:
            self._conn.execute(
                "ALTER TABLE users ADD COLUMN is_read_only INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass
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
            "SELECT id, username, is_admin, is_read_only FROM users ORDER BY id"
        ).fetchall()
        return [
            User(
                id=r["id"],
                username=r["username"],
                is_admin=bool(r["is_admin"]),
                is_read_only=bool(r["is_read_only"]),
            )
            for r in rows
        ]

    def find_user(self, username: str) -> Optional[User]:
        row = self._conn.execute(
            "SELECT id, username, is_admin, is_read_only FROM users"
            " WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
        if row is None:
            return None
        return User(
            id=row["id"],
            username=row["username"],
            is_admin=bool(row["is_admin"]),
            is_read_only=bool(row["is_read_only"]),
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def verify_password(self, username: str, password: str) -> Optional[User]:
        """Return User if credentials are valid, else None."""
        row = self._conn.execute(
            "SELECT id, username, password_hash, is_admin, is_read_only FROM users"
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
                is_read_only=bool(row["is_read_only"]),
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

    def create_user(
        self, username: str, password: str, is_admin: bool = False
    ) -> tuple["User", str]:
        """Create a new user.  Returns (User, plaintext_recovery_code).

        The recovery code is shown to the user exactly once and stored hashed.
        """
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

    def import_viewer_account(
        self, username: str, password_hash: str, recovery_code_hash: str
    ) -> User:
        """Create or refresh a non-admin, read-only account from a viewer package.

        If the username already exists, its credentials and read-only flag
        are overwritten (refreshing a previously imported viewer package).
        """
        existing = self.find_user(username)
        if existing is None:
            cursor = self._conn.execute(
                "INSERT INTO users"
                " (username, password_hash, recovery_code_hash,"
                "  is_admin, is_read_only)"
                " VALUES (?, ?, ?, 0, 1)",
                (username, password_hash, recovery_code_hash),
            )
            self._conn.commit()
            return User(
                id=cursor.lastrowid,
                username=username,
                is_admin=False,
                is_read_only=True,
            )
        self._conn.execute(
            "UPDATE users SET password_hash = ?, recovery_code_hash = ?,"
            " is_admin = 0, is_read_only = 1 WHERE id = ?",
            (password_hash, recovery_code_hash, existing.id),
        )
        self._conn.commit()
        return User(
            id=existing.id, username=username, is_admin=False, is_read_only=True
        )

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
