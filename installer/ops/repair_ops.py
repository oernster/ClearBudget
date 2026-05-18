"""Repair operation using manifest hashes."""

from __future__ import annotations

import hashlib
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path

from installer.ops.errors import AppRunningError, InstallerOperationError
from installer.ops.payload import iter_manifest_entries, load_manifest, payload_zip_path
from installer.ops.running_app import is_app_running
from installer.ops.shortcuts import create_shortcut, get_shortcut_paths
from installer.state.registry import read_uninstall_entry, write_uninstall_entry
from clear_budget.version import APP_AUTHOR, APP_NAME, __version__


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True, slots=True)
class RepairOptions:
    restore_desktop_shortcut: bool
    restore_start_menu_shortcut: bool


def repair(
    identity,
    opts: RepairOptions,
    *,
    progress=None,
    cancel_event=None,
) -> None:  # noqa: ANN001
    if os.name != "nt":
        raise InstallerOperationError("Repair is Windows-only")

    entry = read_uninstall_entry(identity.uninstall_key)
    if entry is None or not entry.install_location.exists():
        raise InstallerOperationError("ClearBudget is not installed")

    install_dir = entry.install_location.resolve()
    exe = install_dir / "ClearBudget.exe"
    if exe.exists() and is_app_running(exe):
        raise AppRunningError("ClearBudget is currently running")

    manifest = load_manifest()
    with zipfile.ZipFile(payload_zip_path(), "r") as zf:
        for e in iter_manifest_entries(manifest):
            if (
                cancel_event is not None
                and getattr(cancel_event, "is_set", lambda: False)()
            ):
                raise InstallerOperationError("Cancelled")
            if progress:
                progress(f"Verifying {e.path}...")
            dst = install_dir / e.path
            needs = True
            if dst.exists():
                try:
                    if dst.stat().st_size == int(e.size):
                        needs = _sha256_file(dst).lower() != str(e.sha256).lower()
                    else:
                        needs = True
                except Exception:
                    needs = True
            if needs:
                if progress:
                    progress(f"Restoring {e.path}...")
                dst.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(e.path) as src, dst.open("wb") as out:
                    out.write(src.read())

    # Restore shortcuts if requested.
    sp = get_shortcut_paths(identity)
    if progress:
        progress("Restoring shortcuts...")
    if opts.restore_desktop_shortcut:
        if not sp.desktop_lnk.exists():
            create_shortcut(exe, sp.desktop_lnk, working_dir=install_dir)
    if opts.restore_start_menu_shortcut:
        if not sp.start_menu_lnk.exists():
            create_shortcut(exe, sp.start_menu_lnk, working_dir=install_dir)

    # Restore uninstall metadata.
    uninstall_cmd = entry.uninstall_string
    if progress:
        progress("Restoring registry metadata...")
    write_uninstall_entry(
        identity.uninstall_key,
        display_name=APP_NAME,
        display_version=entry.display_version or __version__,
        install_location=install_dir,
        uninstall_string=uninstall_cmd,
        display_icon=str(exe),
        publisher=APP_AUTHOR,
        shortcut_desktop=opts.restore_desktop_shortcut,
        shortcut_start_menu=opts.restore_start_menu_shortcut,
        installer_path=entry.installer_path or "",
    )

