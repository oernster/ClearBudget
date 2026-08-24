"""RememberedLogin - remembers sign-in details between runs, by choice.

The password never touches the filesystem. It lives in the operating system's
credential store (Windows Credential Manager, macOS Keychain, Linux Secret
Service) through the ``keyring`` package. The small JSON file in the app
directory records only WHICH accounts are remembered and which of them asked
for their password to be kept, so the app knows what to look up at the next
launch.

Remembering is per ACCOUNT, not one slot for the machine. A household with
several accounts gets each of them offered by name at the sign-in screen,
while each decides separately whether its password is kept: remembering a
username is a convenience, remembering a password is a trust decision, so one
never implies the other. An account that never ticks the box is not listed at
all, so it stays invisible to whoever is at the keyboard.

Every keychain failure (no backend on a bare Linux session, a locked keychain,
a denied prompt) degrades to "nothing remembered": sign-in must never crash or
block because the credential store is unavailable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

# The keychain service name password entries are filed under.
_SERVICE_NAME = "ClearBudget"

# Sidecar file recording WHICH accounts are remembered (never a password).
_STATE_FILENAME = "remembered_login.json"

_ACCOUNTS_KEY = "accounts"
_USERNAME_KEY = "username"
_KEEP_PASSWORD_KEY = "keep_password"
_LAST_KEY = "last"


class SecretBackend(Protocol):
    """The slice of the keyring API this module uses."""

    def set_password(self, service: str, username: str, password: str) -> None: ...

    def get_password(self, service: str, username: str) -> str | None: ...

    def delete_password(self, service: str, username: str) -> None: ...


def _default_backend() -> SecretBackend:
    """The real OS credential store. Imported lazily so tests never touch it."""
    import keyring

    return keyring


@dataclass(frozen=True, slots=True)
class RememberedAccount:
    """One remembered account: its name, plus whether its password is kept."""

    username: str
    keep_password: bool


class RememberedLogin:
    """Remember, recall and forget sign-in details, per account."""

    def __init__(self, state_dir: Path, backend: SecretBackend | None = None) -> None:
        self._state_path = state_dir / _STATE_FILENAME
        self._backend = backend if backend is not None else _default_backend()

    def accounts(self) -> tuple[RememberedAccount, ...]:
        """Every remembered account, in the order they were first remembered."""
        return self._read_state()[0]

    def usernames(self) -> tuple[str, ...]:
        """Just the names, which is what the sign-in screen offers."""
        return tuple(account.username for account in self.accounts())

    def last_username(self) -> str | None:
        """The account that signed in most recently, to preselect it.

        None when nothing is remembered; None too when the account that
        signed in last has since been forgotten.
        """
        accounts, last = self._read_state()
        names = {account.username for account in accounts}
        return last if last in names else None

    def keeps_password(self, username: str) -> bool:
        """Whether `username` asked for its password to be kept."""
        return any(
            account.username == username and account.keep_password
            for account in self.accounts()
        )

    def recall_password(self, username: str) -> str | None:
        """The stored password for `username`; None if there is not one.

        None covers every way this can come up short: the account is not
        remembered, it never asked for its password to be kept, the keychain
        has no entry or the keychain cannot be reached at all.
        """
        if not self.keeps_password(username):
            return None
        try:
            return self._backend.get_password(_SERVICE_NAME, username)
        except Exception:  # noqa: BLE001 (unavailable keychain: not remembered)
            return None

    def remember_username(self, username: str) -> None:
        """Remember `username` without touching whether its password is kept.

        What the checkbox on the account-creation screen writes: there is a
        name to remember at that point but no decision yet about the password,
        which is made on the sign-in screen where the password is typed.
        """
        self._write_account(username, keep_password=None)

    def remember_password(self, username: str, password: str) -> None:
        """Keep `password` for `username`, remembering the username too.

        The sidecar is only updated once the password is safely in the
        keychain, so a failed store never leaves the sign-in screen promising
        a password it cannot produce.
        """
        try:
            self._backend.set_password(_SERVICE_NAME, username, password)
        except Exception:  # noqa: BLE001 (unavailable keychain: not remembered)
            return
        self._write_account(username, keep_password=True)

    def forget_password(self, username: str) -> None:
        """Drop the stored password, keeping the username remembered."""
        self._delete_secret(username)
        self._write_account(username, keep_password=False)

    def forget(self, username: str) -> None:
        """Forget `username` entirely, password included."""
        self._delete_secret(username)
        accounts, last = self._read_state()
        remaining = tuple(a for a in accounts if a.username != username)
        self._write_state(remaining, None if last == username else last)

    def note_signed_in(self, username: str) -> None:
        """Record `username` as the most recent sign-in, if it is remembered.

        Only a remembered account is recorded. Noting one that is not would
        preselect a name the screen does not otherwise admit to knowing.
        """
        accounts, last = self._read_state()
        if any(account.username == username for account in accounts):
            self._write_state(accounts, username)

    def _delete_secret(self, username: str) -> None:
        """Remove the keychain entry, tolerating a store that cannot be had."""
        try:
            self._backend.delete_password(_SERVICE_NAME, username)
        except Exception:  # noqa: BLE001, S110 (already gone; or unreachable)
            pass

    def _write_account(self, username: str, keep_password: bool | None) -> None:
        """Add or update one account; `None` keeps its existing password flag."""
        accounts, last = self._read_state()
        updated = []
        found = False
        for account in accounts:
            if account.username != username:
                updated.append(account)
                continue
            found = True
            keep = account.keep_password if keep_password is None else keep_password
            updated.append(RememberedAccount(username, keep))
        if not found:
            updated.append(RememberedAccount(username, bool(keep_password)))
        self._write_state(tuple(updated), last)

    def _write_state(
        self, accounts: tuple[RememberedAccount, ...], last: str | None
    ) -> None:
        payload = {
            _ACCOUNTS_KEY: [
                {
                    _USERNAME_KEY: account.username,
                    _KEEP_PASSWORD_KEY: account.keep_password,
                }
                for account in accounts
            ],
            _LAST_KEY: last,
        }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(payload), encoding="utf-8")

    def _read_state(self) -> tuple[tuple[RememberedAccount, ...], str | None]:
        """The remembered accounts and the most recent sign-in.

        Reads the single-account file the earlier version wrote as well as the
        current one. That older file is on every machine the app has already
        run on, so failing to understand it would silently forget the login
        somebody is relying on, which reads as the setting having been lost.
        """
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return (), None
        if not isinstance(data, dict):
            return (), None
        if _ACCOUNTS_KEY not in data:
            return self._read_legacy(data)
        accounts = []
        for entry in data.get(_ACCOUNTS_KEY) or ():
            if not isinstance(entry, dict):
                continue
            username = entry.get(_USERNAME_KEY)
            if isinstance(username, str) and username:
                accounts.append(
                    RememberedAccount(username, bool(entry.get(_KEEP_PASSWORD_KEY)))
                )
        last = data.get(_LAST_KEY)
        return tuple(accounts), last if isinstance(last, str) and last else None

    @staticmethod
    def _read_legacy(data: dict) -> tuple[tuple[RememberedAccount, ...], str | None]:
        """Read the one-account-per-machine file the earlier version wrote.

        That version had a single Remember me tick covering both the username
        and the password, so an account recorded there kept its password by
        definition.
        """
        username = data.get(_USERNAME_KEY)
        if not (isinstance(username, str) and username):
            return (), None
        return (RememberedAccount(username, True),), username
