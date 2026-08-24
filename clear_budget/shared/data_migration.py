"""One-time move of the legacy data directory to the platform one.

Runs at startup, before the single-instance lock and the first database
open. The design has one safety property everything else hangs off: the
LEGACY directory's disappearance is the completion signal. Resolution
(`config._choose_app_dir`) prefers the legacy directory while it exists, so
an interrupted migration leaves the app running on the data it always had
and the move is retried at the next launch; nothing is ever half-adopted.

The fast path is a single directory rename, atomic on one volume, which is
the overwhelmingly common case. When rename fails (a cross-volume target),
the tree is copied into a STAGING directory beside the target, verified byte
for byte, renamed into place and only then is the legacy directory renamed
aside and deleted; the rename-aside is atomic, so the legacy directory is
always either whole or gone, never partially deleted. The backup is removed
outright once the move has verified (decided 2026-08-24); a leftover from a
crash between those two steps is swept at the next launch.

A target that already holds a `users.db` is a conflict (a downgraded launch
recreated legacy data after a migration) and is left exactly as found: the
app keeps running on the legacy directory and nothing is merged, because
merging two account databases is not a decision code can make.
"""

from __future__ import annotations

import filecmp
import os
import shutil
from pathlib import Path

# The file whose presence in the target marks it as a live data directory.
_SENTINEL_FILENAME = "users.db"

# Appended to the legacy directory's name while it awaits deletion.
_BACKUP_SUFFIX = ".migrated"

# Appended to the target's name while a copied tree awaits verification.
_STAGING_SUFFIX = ".migrating"


def migrate_legacy_data(
    *, legacy: Path, target: Path, rename=os.rename, copy_tree=shutil.copytree
) -> bool:
    """Move `legacy` to `target`; True when data moved this call.

    `rename` and `copy_tree` are injectable so the cross-volume fallback and
    a corrupt copy are testable with hand-written stand-ins; the app always
    passes the real ones.
    """
    _sweep_leftovers(legacy=legacy, target=target)
    if not legacy.is_dir() or legacy == target:
        return False
    if (target / _SENTINEL_FILENAME).exists():
        return False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_dir():
            # An empty directory left by an earlier crashed attempt.
            target.rmdir()
        rename(legacy, target)
        return True
    except OSError:
        return _copy_migrate(
            legacy=legacy, target=target, rename=rename, copy_tree=copy_tree
        )


def _sweep_leftovers(*, legacy: Path, target: Path) -> None:
    """Remove debris a crash may have left: stale staging, undeleted backup."""
    shutil.rmtree(_staging_dir(target), ignore_errors=True)
    backup = legacy.with_name(legacy.name + _BACKUP_SUFFIX)
    shutil.rmtree(backup, ignore_errors=True)


def _staging_dir(target: Path) -> Path:
    return target.with_name(target.name + _STAGING_SUFFIX)


def _copy_migrate(*, legacy: Path, target: Path, rename, copy_tree) -> bool:
    """Copy, verify, adopt, then retire the legacy directory."""
    staging = _staging_dir(target)
    try:
        copy_tree(legacy, staging)
        if not _trees_match(legacy, staging):
            shutil.rmtree(staging, ignore_errors=True)
            return False
        if target.is_dir():
            target.rmdir()
        rename(staging, target)
        backup = legacy.with_name(legacy.name + _BACKUP_SUFFIX)
        rename(legacy, backup)
        shutil.rmtree(backup, ignore_errors=True)
        return True
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        return False


def _trees_match(source: Path, copy: Path) -> bool:
    """Every file under `source` exists under `copy` with identical bytes."""
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        counterpart = copy / path.relative_to(source)
        if not counterpart.is_file():
            return False
        if not filecmp.cmp(path, counterpart, shallow=False):
            return False
    return True
