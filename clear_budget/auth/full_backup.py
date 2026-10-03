"""Back up and restore EVERYTHING: accounts plus every budget.

File > Save covers only the active budget; `users.db` (usernames, password
and recovery-code hashes, the admin flag) sat outside every backup path the
app offered, so losing the data directory meant recreating every account by
hand. This module bundles the whole identity-and-data set into one zip:
`users.db`, every `budget_*.db` for every user and budget and the
`budgets_*.json` registry sidecars. Caches are excluded (regenerated) and so
is the Remember-me sidecar: the password it refers to lives in the OS
keychain and cannot travel in a file. Each database goes in as a SNAPSHOT
taken through SQLite, never as a copy of its bytes, because the app holds at
least two of them open while the backup runs.

Restore is validated before a single live file is touched: the zip's members
are extracted to a staging directory inside the data directory; a member
named twice (in any letter case) is refused; the accounts database must hold
the columns sign-in reads; each budget database is schema-checked; every
database is read page by page; each budget list must parse and name only
files the app could have written. Only then are the live files replaced, file
by file, each with its SQLite sidecars; all are put back if any step fails.
Afterwards the budgets and budget lists that belong to no restored account
are moved to a quarantine folder inside the data directory, never deleted,
so a new account given an old name cannot inherit the old one's figures.

The caller must have closed every open connection first (on Windows an open
database cannot be replaced); the UI flow tears the session down and returns
to the sign-in screen.

The backup is as unencrypted as everything else at rest. It carries bcrypt
HASHES rather than passwords; it is still every account and every budget in
one portable file: treat it like the data directory itself.
"""

from __future__ import annotations

import fnmatch
import os
import shutil
import sqlite3
import tempfile
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from clear_budget.shared import budget_files
from clear_budget.shared.budget_files import (
    BUDGET_DB_PATTERN,
    BUDGET_LIST_PATTERN,
    belongs_to,
    estate_files,
    with_sidecars,
)
from clear_budget.shared.budget_registry import index_text_error
from clear_budget.shared.db_copy import DatabaseCopyError, snapshot_database_file
from clear_budget.shared.db_validation import validate_accounts_db, validate_db

USERS_DB_NAME = "users.db"
_STAGING_DIR_NAME = "_restore_staging"
# What a live file is renamed to while its replacement moves in, so a
# failure part way through can be undone.
_DISPLACED_SUFFIX = ".pre_restore"
# Names the quarantine folder a restore creates.
_QUARANTINE_REASON = "restore"
_DB_SUFFIX = ".db"
_TEXT_ENCODING = "utf-8"

# Everything reading a damaged archive's member data can raise. The
# directory of a damaged zip often reads perfectly, so validation passes
# and the damage only shows when a member is decompressed.
_ARCHIVE_DAMAGE = (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError)


class FullBackupError(ValueError):
    """A backup or restore that cannot proceed; the message says why."""


@dataclass(frozen=True, slots=True)
class RestoreResult:
    """What a restore put in place and what it moved to quarantine."""

    names: list[str]
    quarantined: list[str] = field(default_factory=list)
    quarantine_dir: Path | None = None


def create_full_backup(*, app_dir: Path, dest_path: Path) -> list[str]:
    """Write the full-backup zip to ``dest_path``; return the names bundled.

    The zip is built beside the destination and renamed over it, so a backup
    that fails part way leaves no half-written file behind.
    """
    users_db = app_dir / USERS_DB_NAME
    if not users_db.is_file():
        raise FullBackupError("There is no accounts database to back up.")
    names = [
        USERS_DB_NAME,
        *sorted(p.name for p in app_dir.glob(BUDGET_DB_PATTERN) if p.is_file()),
        *sorted(p.name for p in app_dir.glob(BUDGET_LIST_PATTERN) if p.is_file()),
    ]
    handle, scratch_name = tempfile.mkstemp(
        dir=str(dest_path.parent), prefix=dest_path.name + "."
    )
    os.close(handle)
    scratch = Path(scratch_name)
    try:
        with tempfile.TemporaryDirectory(dir=str(dest_path.parent)) as snaps:
            with zipfile.ZipFile(scratch, "w", zipfile.ZIP_DEFLATED) as zf:
                for name in names:
                    zf.write(_bundled_copy(app_dir / name, Path(snaps)), name)
        os.replace(scratch, dest_path)
    finally:
        # Gone already when the rename landed; otherwise the partial zip.
        scratch.unlink(missing_ok=True)
    return names


def _bundled_copy(path: Path, snaps: Path) -> Path:
    """The file to put in the zip for ``path``: a snapshot for a database."""
    if not path.name.endswith(_DB_SUFFIX):
        return path
    snapshot = snaps / path.name
    try:
        snapshot_database_file(path, snapshot)
    except DatabaseCopyError as exc:
        raise FullBackupError(
            f"'{path.name}' could not be read for the backup ({exc}). Nothing "
            "was written. If a budget is busy saving, try again in a moment."
        ) from exc
    return snapshot


def _is_permitted_member(name: str) -> bool:
    """Only flat files with the exact names a data directory can contain."""
    if "/" in name or "\\" in name or name.startswith(".."):
        return False
    return name == USERS_DB_NAME or (
        fnmatch.fnmatch(name, BUDGET_DB_PATTERN)
        or fnmatch.fnmatch(name, BUDGET_LIST_PATTERN)
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
    _refuse_duplicates(names)
    return names


def _refuse_duplicates(names: list[str]) -> None:
    """Refuse a name that appears twice, in any letter case.

    Two entries for one file would both be restored over it, the second
    overwriting what the first had saved (measured: a live budget lost). On
    Windows `BUDGET_ALICE.db` and `budget_alice.db` ARE one file.
    """
    seen: set[str] = set()
    for name in names:
        key = name.casefold()
        if key in seen:
            raise FullBackupError(
                f"Not a usable backup: '{name}' appears more than once."
            )
        seen.add(key)


def restore_full_backup(*, package_path: Path, app_dir: Path) -> RestoreResult:
    """Replace the live accounts and budgets with the backup's.

    Every open connection must be closed before this is called. Validation
    happens entirely in a staging directory, so a malformed backup changes
    nothing; the final per-file replacement is the only step that touches
    live data and it is undone if it fails part way.
    """
    names = validate_full_backup(package_path)
    staging = app_dir / _STAGING_DIR_NAME
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        _extract(package_path, names, staging)
        _check_staged(names, staging)
        accounts = _account_names(staging / USERS_DB_NAME)
        _replace_all(names, staging=staging, app_dir=app_dir)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    orphans = [
        path
        for path in estate_files(app_dir)
        if not any(belongs_to(path, account) for account in accounts)
    ]
    folder, moved = budget_files.quarantine(
        orphans, app_dir=app_dir, reason=_QUARANTINE_REASON
    )
    return RestoreResult(names=names, quarantined=moved, quarantine_dir=folder)


def _extract(package_path: Path, names: list[str], staging: Path) -> None:
    """Write every member into ``staging``; a damaged archive is refused."""
    try:
        with zipfile.ZipFile(package_path, "r") as zf:
            for name in names:
                with zf.open(name) as src, open(staging / name, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    except _ARCHIVE_DAMAGE as exc:
        raise FullBackupError(
            f"The backup file is damaged, so nothing was changed ({exc})."
        ) from exc


def _check_staged(names: list[str], staging: Path) -> None:
    """Raise FullBackupError for the first staged file the app cannot use."""
    error = validate_accounts_db(staging / USERS_DB_NAME)
    if error:
        raise FullBackupError(error)
    for name in names:
        error = None
        if fnmatch.fnmatch(name, BUDGET_DB_PATTERN):
            error = validate_db(staging / name)
        elif fnmatch.fnmatch(name, BUDGET_LIST_PATTERN):
            raw = (staging / name).read_bytes()
            error = index_text_error(raw.decode(_TEXT_ENCODING, errors="replace"))
        if error:
            raise FullBackupError(f"'{name}' in the backup: {error}")


def _account_names(users_db: Path) -> list[str]:
    """The usernames in a validated accounts database.

    Closed explicitly: sqlite3's context manager commits but does NOT close
    and an open handle makes Windows refuse the replace that follows.
    """
    conn = sqlite3.connect(f"file:{users_db}?mode=ro", uri=True)
    try:
        return [row[0] for row in conn.execute("SELECT username FROM users")]
    finally:
        conn.close()


def _replace_all(names: list[str], *, staging: Path, app_dir: Path) -> None:
    """Move every staged file into place; else put back what was there before.

    The replacement is file by file, so a failure half way through used to
    leave the accounts database swapped and the budgets not: every account
    from the backup, every budget from before it, which is a state neither
    the user nor the app has any way to reason about. It is not theoretical.
    A stray read handle on one budget was measured taking a restore down at
    exactly that point.

    There is no atomic multi-file replace, so the next best thing is an undo:
    each live file is moved aside first (with its SQLite sidecars) and moved
    back if anything raises. A sidecar left behind is a crash journal that
    SQLite plays back over the restored file at the next open (measured).
    Every aside path is unique to its position in the list, so nothing can
    overwrite a saved original; the undo runs in reverse, so a file moved
    aside twice ends as it began.
    """
    displaced: list[tuple[Path, Path]] = []
    try:
        for position, name in enumerate(names):
            for current in with_sidecars(app_dir / name):
                aside = staging / f"{current.name}.{position}{_DISPLACED_SUFFIX}"
                current.replace(aside)
                displaced.append((aside, current))
            (staging / name).replace(app_dir / name)
    except OSError:
        # Unconditional: a file whose replacement already landed is exactly
        # the one that must be put back, so testing whether it exists would
        # skip every case worth undoing.
        for aside, live in reversed(displaced):
            aside.replace(live)
        raise
