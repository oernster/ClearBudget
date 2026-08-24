"""Back up and restore EVERYTHING: accounts plus every budget.

File > Save covers only the active budget; `users.db` (usernames, password
and recovery-code hashes, the admin flag) sat outside every backup path the
app offered, so losing the data directory meant recreating every account by
hand. This module bundles the whole identity-and-data set into one zip:
`users.db`, every `budget_*.db` for every user and budget and the
`budgets_*.json` registry sidecars. Caches are excluded (regenerated) and so
is the Remember-me sidecar: the password it refers to lives in the OS
keychain and cannot travel in a file.

Restore is validated before a single live file is touched: the zip's members
are extracted to a staging directory inside the data directory, each budget
database is schema-checked and the accounts database is confirmed to hold a
users table; only then are the live files replaced, file by file. The caller
must have closed every open connection first (on Windows an open database
cannot be replaced); the UI flow tears the session down and returns to the
sign-in screen.

The backup is as unencrypted as everything else at rest. It carries bcrypt
HASHES rather than passwords; it is still every account and every budget in
one portable file: treat it like the data directory itself.
"""

from __future__ import annotations

import fnmatch
import shutil
import sqlite3
import zipfile
from pathlib import Path

from clear_budget.shared.db_validation import validate_db

USERS_DB_NAME = "users.db"
_BUDGET_PATTERN = "budget_*.db"
_SIDECAR_PATTERN = "budgets_*.json"
_STAGING_DIR_NAME = "_restore_staging"


class FullBackupError(ValueError):
    """A backup or restore that cannot proceed; the message says why."""


def create_full_backup(*, app_dir: Path, dest_path: Path) -> list[str]:
    """Write the full-backup zip to ``dest_path``; return the names bundled."""
    users_db = app_dir / USERS_DB_NAME
    if not users_db.is_file():
        raise FullBackupError("There is no accounts database to back up.")
    names = [
        USERS_DB_NAME,
        *sorted(p.name for p in app_dir.glob(_BUDGET_PATTERN) if p.is_file()),
        *sorted(p.name for p in app_dir.glob(_SIDECAR_PATTERN) if p.is_file()),
    ]
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in names:
            zf.write(app_dir / name, name)
    return names


def _is_permitted_member(name: str) -> bool:
    """Only flat files with the exact names a data directory can contain."""
    if "/" in name or "\\" in name or name.startswith(".."):
        return False
    return name == USERS_DB_NAME or (
        fnmatch.fnmatch(name, _BUDGET_PATTERN)
        or fnmatch.fnmatch(name, _SIDECAR_PATTERN)
    )


def validate_full_backup(package_path: Path) -> list[str]:
    """The member names of a well-formed backup; raise FullBackupError else.

    Shape only: the databases themselves are checked at restore time, once
    they are bytes on disk rather than entries in an archive.
    """
    try:
        with zipfile.ZipFile(package_path, "r") as zf:
            names = zf.namelist()
    except (OSError, zipfile.BadZipFile) as exc:
        raise FullBackupError("Not a readable backup file.") from exc
    if USERS_DB_NAME not in names:
        raise FullBackupError("Not a ClearBudget full backup: no accounts database.")
    strays = [n for n in names if not _is_permitted_member(n)]
    if strays:
        raise FullBackupError(
            "Not a ClearBudget full backup: unexpected entry "
            f"'{strays[0]}' in the archive."
        )
    return names


def _users_db_error(path: Path) -> str | None:
    """None when ``path`` is an accounts database; else what is wrong.

    The connection is closed explicitly: sqlite3's context manager commits
    but does NOT close; a connection left open on the staged file makes
    Windows refuse the replace into the live directory.
    """
    try:
        conn = sqlite3.connect(str(path))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return "The accounts database in the backup is not readable."
    if row is None:
        return "The accounts database in the backup holds no users table."
    return None


def restore_full_backup(*, package_path: Path, app_dir: Path) -> list[str]:
    """Replace the live accounts and budgets with the backup's; return names.

    Every open connection must be closed before this is called. Validation
    happens entirely in a staging directory, so a malformed backup changes
    nothing; the final per-file replacement is the only step that touches
    live data.
    """
    names = validate_full_backup(package_path)
    staging = app_dir / _STAGING_DIR_NAME
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        with zipfile.ZipFile(package_path, "r") as zf:
            for name in names:
                with zf.open(name) as src, open(staging / name, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        error = _users_db_error(staging / USERS_DB_NAME)
        if error:
            raise FullBackupError(error)
        for name in names:
            if fnmatch.fnmatch(name, _BUDGET_PATTERN):
                budget_error = validate_db(staging / name)
                if budget_error:
                    raise FullBackupError(f"'{name}' in the backup: {budget_error}")
        for name in names:
            (staging / name).replace(app_dir / name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return names
