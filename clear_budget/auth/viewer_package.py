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
    package_path: Path, user_store: UserStore, config: Config | None = None
) -> User:
    """Create or refresh a read-only account from package_path and install its data.

    Returns the created/refreshed User.  Raises ValueError if the package is
    malformed or its database is not a valid ClearBudget database.

    ``config`` defaults to ``Config.for_user(username)``; pass an explicit
    Config to redirect the installed database elsewhere (e.g. in tests).
    """
    with zipfile.ZipFile(package_path, "r") as zf:
        names = zf.namelist()
        if _ACCOUNT_ENTRY_NAME not in names or _DB_ENTRY_NAME not in names:
            raise ValueError("Not a valid viewer package.")
        try:
            account = json.loads(zf.read(_ACCOUNT_ENTRY_NAME).decode())
            username = account["username"]
            password_hash = account["password_hash"]
            recovery_code_hash = account["recovery_code_hash"]
        except (json.JSONDecodeError, KeyError) as exc:
            raise ValueError("Not a valid viewer package.") from exc

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
