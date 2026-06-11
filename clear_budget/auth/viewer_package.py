"""Export/import read-only viewer packages.

A viewer package is a zip file bundling a snapshot of a budget database
together with credentials for a new (or refreshed) read-only account.  It
lets an admin hand a family member a single file that, once imported on
their own machine, gives them a read-only copy of the admin's data under a
username/password the admin chose.
"""

import json
import shutil
import zipfile
from pathlib import Path

from clear_budget.auth.models import User
from clear_budget.auth.user_store import UserStore
from clear_budget.shared.config import Config
from clear_budget.shared.db_validation import validate_db

_DB_ENTRY_NAME = "data.db"
_ACCOUNT_ENTRY_NAME = "account.json"


class UsernameClashError(ValueError):
    """Raised when an imported viewer package's username is already in use
    by an existing account on this machine.

    ``existing_is_viewer`` is True if the existing account is itself a
    read-only viewer account (so the caller may offer to refresh it instead
    of choosing a new username); False if it's a real account that must
    never be silently overwritten.
    """

    def __init__(self, username: str, existing_is_viewer: bool) -> None:
        self.username = username
        self.existing_is_viewer = existing_is_viewer
        super().__init__(f"Username '{username}' is already in use on this machine.")


def export_viewer_package(
    db_path: Path, dest_path: Path, username: str, password: str
) -> None:
    """Bundle a snapshot of db_path plus new viewer credentials into dest_path."""
    account = {
        "username": username,
        "password_hash": UserStore.hash_password(password),
        "recovery_code_hash": UserStore.generate_recovery_code()[1],
    }
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_path, _DB_ENTRY_NAME)
        zf.writestr(_ACCOUNT_ENTRY_NAME, json.dumps(account))


def import_viewer_package(
    package_path: Path,
    user_store: UserStore,
    config: Config | None = None,
    username_override: str | None = None,
    refresh: bool = False,
) -> User:
    """Create or refresh a read-only account from package_path and install its data.

    Returns the created/refreshed User.  Raises ValueError if the package is
    malformed or its database is not a valid ClearBudget database.

    If the package's username (or ``username_override``, if given) already
    belongs to an existing account on this machine, raises
    ``UsernameClashError`` instead of silently overwriting it. Callers should
    then either re-invoke with ``username_override`` set to a username chosen
    by the importing user, or - only if ``UsernameClashError.existing_is_viewer``
    is True - re-invoke with ``refresh=True`` to update that viewer account's
    credentials and data in place. A real (non-viewer) account can never be
    overwritten, regardless of ``refresh``.

    ``config`` defaults to ``Config.for_user(username)``; pass an explicit
    Config to redirect the installed database elsewhere (e.g. in tests).
    """
    with zipfile.ZipFile(package_path, "r") as zf:
        names = zf.namelist()
        if _ACCOUNT_ENTRY_NAME not in names or _DB_ENTRY_NAME not in names:
            raise ValueError("Not a valid viewer package.")
        try:
            account = json.loads(zf.read(_ACCOUNT_ENTRY_NAME).decode())
            username = username_override or account["username"]
            password_hash = account["password_hash"]
            recovery_code_hash = account["recovery_code_hash"]
        except (json.JSONDecodeError, KeyError) as exc:
            raise ValueError("Not a valid viewer package.") from exc

        existing = user_store.find_user(username)
        if existing is not None and not (refresh and existing.is_read_only):
            raise UsernameClashError(username, existing_is_viewer=existing.is_read_only)

        if config is None:
            config = Config.for_user(username)
        config.ensure_directories()
        tmp_db_path = config.db_path.with_suffix(".tmp")
        with zf.open(_DB_ENTRY_NAME) as src, open(tmp_db_path, "wb") as dst:
            shutil.copyfileobj(src, dst)

    validation_error = validate_db(tmp_db_path)
    if validation_error:
        tmp_db_path.unlink(missing_ok=True)
        raise ValueError(validation_error)

    user = user_store.import_viewer_account(username, password_hash, recovery_code_hash)
    tmp_db_path.replace(config.db_path)
    return user
