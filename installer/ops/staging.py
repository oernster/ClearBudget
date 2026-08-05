"""Staging a new bundle and swapping it into place.

The payload is never extracted over a live install. It goes into a staging
directory beside the target, so the move into place is a same-volume rename:
one operation; the previous install stays intact until it succeeds. The
previous install is renamed aside rather than deleted, so a failure part way
through can put it back.

British spelling is used in comments.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from installer.constants import STAGING_PREFIX
from installer.ops.errors import InstallerOperationError

logger = logging.getLogger("installer.install")

# Enough of a uuid to make a collision between two concurrent runs implausible
# while keeping the path short, since the whole install path sits under it.
_BACKUP_SUFFIX_CHARS = 8

CANCELLED_MESSAGE = "Cancelled"
_IS_SET = "is_set"


def check_cancel(cancel_event) -> None:
    """Raise when the user has asked to stop, otherwise return."""
    if cancel_event is not None and getattr(cancel_event, _IS_SET, lambda: False)():
        raise InstallerOperationError(CANCELLED_MESSAGE)


def staging_dir_for(target_dir: Path, purpose: str) -> Path:
    """Return a fresh staging directory beside ``target_dir``.

    Any stale directory left at that name by an interrupted run is removed
    first, so a retry never merges two extractions.
    """
    staging_dir = target_dir.parent / f"{STAGING_PREFIX}.{purpose}.{uuid.uuid4().hex}"
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    return staging_dir


def swap_in_bundle(staging_dir: Path, target_dir: Path) -> None:
    """Replace ``target_dir`` with ``staging_dir``.

    Uses a same-volume rename when possible and falls back to copytree when the
    install target lives on a different volume from the staging area.
    """
    target_dir = target_dir.resolve()
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Swapping bundle into %s (staging=%s)", target_dir, staging_dir)

    backup_dir = _move_existing_aside(target_dir)

    try:
        try:
            staging_dir.rename(target_dir)
        except OSError:
            # Likely a cross-volume move, which rename cannot do. Copy instead.
            shutil.copytree(staging_dir, target_dir, dirs_exist_ok=False)
            shutil.rmtree(staging_dir, ignore_errors=True)
    except Exception:
        _restore(backup_dir, target_dir)
        raise
    finally:
        if backup_dir is not None and backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)


def _move_existing_aside(target_dir: Path) -> Path | None:
    """Rename any existing install out of the way, returning where it went."""
    if not target_dir.exists():
        return None
    backup_dir = target_dir.with_name(
        target_dir.name + f".old.{uuid.uuid4().hex[:_BACKUP_SUFFIX_CHARS]}"
    )
    try:
        target_dir.rename(backup_dir)
    except OSError as exc:
        raise InstallerOperationError(
            f"Unable to replace existing install at {target_dir}"
        ) from exc
    return backup_dir


def _restore(backup_dir: Path | None, target_dir: Path) -> None:
    """Put the previous install back after a failed swap, best effort.

    Best effort because the swap has already failed: the caller is about to
    raise; a restore that also fails must not replace that error with a
    less informative one.
    """
    if backup_dir is None or not backup_dir.exists() or target_dir.exists():
        return
    try:
        backup_dir.rename(target_dir)
    except OSError:
        logger.exception("Failed restoring the previous install at %s", target_dir)
