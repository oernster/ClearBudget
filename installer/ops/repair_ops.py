"""Repair: restore any file that has gone missing or been altered.

The payload manifest records a size and a SHA-256 for every file in the
bundle, so a repair walks it, checks each file on disk and rewrites only the
ones that no longer match. The manifest's length is known before the walk
starts, so the operation reports real per-entry progress rather than a bare
message.

Every destination is resolved through the same guard the extraction uses, so a
manifest path can only ever write inside the install directory. British
spelling is used in comments.
"""

from __future__ import annotations

import hashlib
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path

from clear_budget.version import APP_AUTHOR, APP_NAME, __version__
from installer.constants import InstallerIdentity
from installer.ops.errors import AppRunningError, InstallerOperationError
from installer.ops.legacy import cleanup_orphaned_legacy_install
from installer.ops.payload import (
    ManifestEntry,
    iter_manifest_entries,
    load_manifest,
    payload_zip_path,
    safe_destination,
)
from installer.ops.progress import (
    COMPLETE_PCT,
    DONE_MESSAGE,
    REPAIR_CLEANUP_MESSAGE,
    REPAIR_CLEANUP_PCT,
    RESTORE_MESSAGE_TEMPLATE,
    RESTORE_REGISTRY_MESSAGE,
    RESTORE_REGISTRY_PCT,
    RESTORE_SHORTCUTS_MESSAGE,
    RESTORE_SHORTCUTS_PCT,
    VERIFY_END_PCT,
    VERIFY_MESSAGE_TEMPLATE,
    VERIFY_START_PCT,
    ProgressCallback,
    report,
    scaled,
)
from installer.ops.registration import installed_exe
from installer.ops.running_app import ProcessController, is_app_running
from installer.ops.shortcuts import create_shortcut, get_shortcut_paths
from installer.ops.staging import check_cancel
from installer.state.registry import read_uninstall_entry, write_uninstall_entry

# Hashing is done in chunks so a large bundle file never has to be held whole
# in memory to be verified.
_HASH_CHUNK_BYTES = 1024 * 1024

WINDOWS_ONLY_MESSAGE = "Repair is Windows-only"
NOT_INSTALLED_MESSAGE = "Clear Budget is not installed"
APP_RUNNING_MESSAGE = "Clear Budget is currently running"

_WINDOWS_OS_NAME = "nt"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_HASH_CHUNK_BYTES), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True, slots=True)
class RepairOptions:
    restore_desktop_shortcut: bool
    restore_start_menu_shortcut: bool


def needs_restoring(dst: Path, entry: ManifestEntry) -> bool:
    """Return True when the file on disk does not match the manifest entry.

    A file that cannot be read is treated as needing restoration, which is the
    safe direction: rewriting a good file costs a copy, whereas leaving a bad
    one in place is the failure a repair exists to fix.
    """
    if not dst.exists():
        return True
    try:
        if dst.stat().st_size != int(entry.size):
            return True
        return _sha256_file(dst).lower() != str(entry.sha256).lower()
    except OSError:
        return True


def _restore_files(
    install_dir: Path,
    entries: tuple[ManifestEntry, ...],
    *,
    progress: ProgressCallback | None,
    cancel_event,
) -> None:
    """Verify every manifest entry and rewrite the ones that do not match."""
    total = len(entries)
    with zipfile.ZipFile(payload_zip_path(), "r") as zf:
        for done, entry in enumerate(entries, start=1):
            check_cancel(cancel_event)
            pct = scaled(done, total, VERIFY_START_PCT, VERIFY_END_PCT)
            report(progress, pct, VERIFY_MESSAGE_TEMPLATE.format(path=entry.path))

            dst = safe_destination(install_dir, entry.path)
            if not needs_restoring(dst, entry):
                continue

            report(progress, pct, RESTORE_MESSAGE_TEMPLATE.format(path=entry.path))
            dst.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(entry.path) as src, dst.open("wb") as out:
                out.write(src.read())


def repair(
    identity: InstallerIdentity,
    opts: RepairOptions,
    *,
    progress=None,
    cancel_event=None,
    controller: ProcessController | None = None,
) -> None:
    if os.name != _WINDOWS_OS_NAME:
        raise InstallerOperationError(WINDOWS_ONLY_MESSAGE)

    entry = read_uninstall_entry(identity.uninstall_key)
    if entry is None or not entry.install_location.exists():
        raise InstallerOperationError(NOT_INSTALLED_MESSAGE)

    install_dir = entry.install_location.resolve()
    exe = installed_exe(install_dir)
    if exe.exists() and is_app_running(exe, controller):
        raise AppRunningError(APP_RUNNING_MESSAGE)

    entries = tuple(iter_manifest_entries(load_manifest()))
    _restore_files(install_dir, entries, progress=progress, cancel_event=cancel_event)

    report(progress, RESTORE_SHORTCUTS_PCT, RESTORE_SHORTCUTS_MESSAGE)
    sp = get_shortcut_paths(identity)
    if opts.restore_desktop_shortcut and not sp.desktop_lnk.exists():
        create_shortcut(exe, sp.desktop_lnk, working_dir=install_dir)
    if opts.restore_start_menu_shortcut and not sp.start_menu_lnk.exists():
        create_shortcut(exe, sp.start_menu_lnk, working_dir=install_dir)

    report(progress, RESTORE_REGISTRY_PCT, RESTORE_REGISTRY_MESSAGE)
    write_uninstall_entry(
        identity.uninstall_key,
        display_name=APP_NAME,
        display_version=entry.display_version or __version__,
        install_location=install_dir,
        uninstall_string=entry.uninstall_string,
        display_icon=str(exe),
        publisher=APP_AUTHOR,
        shortcut_desktop=opts.restore_desktop_shortcut,
        shortcut_start_menu=opts.restore_start_menu_shortcut,
        installer_path=entry.installer_path or "",
    )

    # Remove the pre-rename orphan install dir (a no-op once it is gone), so a
    # repair leaves the machine as clean as a fresh install or upgrade does.
    report(progress, REPAIR_CLEANUP_PCT, REPAIR_CLEANUP_MESSAGE)
    cleanup_orphaned_legacy_install(install_dir)

    report(progress, COMPLETE_PCT, DONE_MESSAGE)
