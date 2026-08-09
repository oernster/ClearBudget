"""RememberedLogin - persists sign-in credentials between runs, by choice.

The password never touches the filesystem: it lives in the operating system's
credential store (Windows Credential Manager, macOS Keychain, Linux Secret
Service) through the ``keyring`` package. Only the remembered username is
written to a small JSON file in the app directory, so the app knows which
keychain entry to look up at the next launch.

Every keychain failure (no backend on a bare Linux session, a locked keychain,
a denied prompt) degrades to "nothing remembered": sign-in must never crash or
block because the credential store is unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

# The keychain service name the password entry is filed under.
_SERVICE_NAME = "ClearBudget"

# Sidecar file recording WHICH username is remembered (never the password).
_STATE_FILENAME = "remembered_login.json"

_USERNAME_KEY = "username"


class SecretBackend(Protocol):
    """The slice of the keyring API this module uses."""

    def set_password(self, service: str, username: str, password: str) -> None: ...

    def get_password(self, service: str, username: str) -> str | None: ...

    def delete_password(self, service: str, username: str) -> None: ...


def _default_backend() -> SecretBackend:
    """The real OS credential store. Imported lazily so tests never touch it."""
    import keyring

    return keyring


class RememberedLogin:
    """Remember, recall and forget one set of sign-in credentials."""

    def __init__(self, state_dir: Path, backend: SecretBackend | None = None) -> None:
        self._state_path = state_dir / _STATE_FILENAME
        self._backend = backend if backend is not None else _default_backend()

    def recall(self) -> tuple[str, str] | None:
        """Return (username, password) if remembered and retrievable, else None."""
        username = self._read_username()
        if username is None:
            return None
        try:
            password = self._backend.get_password(_SERVICE_NAME, username)
        except Exception:  # noqa: BLE001 (unavailable keychain: not remembered)
            return None
        if password is None:
            return None
        return username, password

    def remember(self, username: str, password: str) -> None:
        """Store credentials for the next launch.

        The username sidecar is only written once the password is safely in the
        keychain, so a failed store never leaves a dangling half-state.
        """
        try:
            self._backend.set_password(_SERVICE_NAME, username, password)
        except Exception:  # noqa: BLE001 (unavailable keychain: not remembered)
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps({_USERNAME_KEY: username}), encoding="utf-8"
        )

    def forget(self) -> None:
        """Delete any remembered credentials from keychain and disk."""
        username = self._read_username()
        if username is not None:
            # Entry already gone or keychain unavailable: the sidecar removal
            # below must still run, so the failure is swallowed deliberately.
            try:
                self._backend.delete_password(_SERVICE_NAME, username)
            except Exception:  # noqa: BLE001, S110
                pass
        self._state_path.unlink(missing_ok=True)

    def _read_username(self) -> str | None:
        """The remembered username from the sidecar; None if absent or corrupt."""
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        username = data.get(_USERNAME_KEY) if isinstance(data, dict) else None
        return username if isinstance(username, str) and username else None
