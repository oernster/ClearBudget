"""Install / upgrade / reinstall operations."""

from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import logging

from platformdirs import user_data_dir

from installer.constants import InstallerIdentity
from installer.ops.errors import AppRunningError, InstallerOperationError
from installer.ops.legacy import (
    cleanup_orphaned_legacy_install,
    migrate_legacy_appdata_dirs,
)
from installer.ops.payload import payload_zip_path
from installer.ops.running_app import is_app_running
from installer.ops.shortcuts import create_shortcut, get_shortcut_paths
from installer.state.registry import write_uninstall_entry
from clear_budget.shared.resources import find_app_icon_path
from clear_budget.version import APP_NAME, APP_AUTHOR, __version__

logger = logging.getLogger("installer.install")


def _progress(progress, *, pct: int | None, message: str) -> None:  # noqa: ANN001
    if not progress:
        return
    if pct is None:
        progress(message)
    else:
        progress({"pct": int(pct), "message": message})


ProgressCb = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class InstallOptions:
    target_dir: Path
    create_desktop_shortcut: bool
    create_start_menu_shortcut: bool


def _installer_staging_root() -> Path:
    local = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "ClearBudgetInstaller" / "staging"


def _extract_payload_to(
    staging_dir: Path, *, progress=None, cancel_event=None
) -> None:  # noqa: ANN001
    staging_dir.mkdir(parents=True, exist_ok=True)
    _check_cancel(cancel_event)
    _progress(progress, pct=10, message="Extracting payload...")
    logger.info("Extracting payload to %s", staging_dir)
    with zipfile.ZipFile(payload_zip_path(), "r") as zf:
        zf.extractall(staging_dir)

    _check_cancel(cancel_event)

    exe = staging_dir / "ClearBudget.exe"
    internal = staging_dir / "_internal"
    if not exe.exists() or not internal.exists():
        raise InstallerOperationError(
            "Payload is missing ClearBudget.exe or _internal/"
        )


def _swap_in_bundle(staging_dir: Path, target_dir: Path) -> None:
    """Replace target_dir with staging_dir.

    Uses a same-volume rename when possible; falls back to copytree when
    installing across different volumes.
    """

    target_dir = target_dir.resolve()
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Swapping bundle into %s (staging=%s)", target_dir, staging_dir)

    backup_dir: Path | None = None
    if target_dir.exists():
        backup_dir = target_dir.with_name(
            target_dir.name + f".old.{uuid.uuid4().hex[:8]}"
        )
        try:
            target_dir.rename(backup_dir)
        except Exception as exc:
            raise InstallerOperationError(
                f"Unable to replace existing install at {target_dir}"
            ) from exc

    try:
        try:
            staging_dir.rename(target_dir)
        except OSError:
            # Likely cross-volume move. Copy instead.
            shutil.copytree(staging_dir, target_dir, dirs_exist_ok=False)
            shutil.rmtree(staging_dir, ignore_errors=True)
    except Exception:
        # Rollback.
        if backup_dir and backup_dir.exists() and not target_dir.exists():
            try:
                backup_dir.rename(target_dir)
            except Exception:
                pass
        raise
    finally:
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)


def _check_cancel(cancel_event) -> None:  # noqa: ANN001
    if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
        raise InstallerOperationError("Cancelled")


def _copy_self_to_install(identity: InstallerIdentity, install_dir: Path) -> Path:
    install_dir = install_dir.resolve()
    dst = identity.installer_exe_path(install_dir)
    dst.parent.mkdir(parents=True, exist_ok=True)

    src = Path(sys.executable).resolve()
    logger.info("Copying installer from %s to %s", src, dst)
    shutil.copy2(src, dst)
    return dst


def _register_uninstall(
    identity: InstallerIdentity,
    *,
    install_dir: Path,
    installer_copy: Path,
    shortcut_desktop: bool,
    shortcut_start_menu: bool,
) -> None:
    exe = install_dir / "ClearBudget.exe"
    uninstall_cmd = f'"{installer_copy}" --uninstall'

    # Use multi-resolution ICO if available.
    display_icon = str(exe)
    for ico_name in ["clearbudget.ico", "ClearBudget.ico"]:
        ico_path = install_dir / ico_name
        if ico_path.exists():
            display_icon = str(ico_path)
            break

    write_uninstall_entry(
        identity.uninstall_key,
        display_name=APP_NAME,
        display_version=__version__,
        install_location=install_dir,
        uninstall_string=uninstall_cmd,
        display_icon=display_icon,
        publisher=APP_AUTHOR,
        shortcut_desktop=shortcut_desktop,
        shortcut_start_menu=shortcut_start_menu,
        installer_path=str(installer_copy),
    )


def _deploy_runtime_icon_assets(*, install_dir: Path) -> None:
    """Deploy icon assets next to ClearBudget.exe.

    - ICO (multi-resolution): for shortcuts via shell API
    - PNGs: for Qt runtime fallback if ICO unavailable
    """

    project_root = Path(__file__).resolve().parents[2]

    # Deploy the multi-resolution ICO file for shortcuts.
    ico = find_app_icon_path(project_root=project_root)
    if ico is not None:
        try:
            shutil.copy2(ico, install_dir / "clearbudget.ico")
        except Exception:
            pass

    # Also deploy PNG assets (best-effort for Qt runtime fallback).
    for name in [
        "clearbudget_16.png",
        "clearbudget_32.png",
        "clearbudget_48.png",
        "clearbudget_64.png",
        "clearbudget_128.png",
        "clearbudget_256.png",
        "clearbudget_512.png",
    ]:
        src = project_root / name
        if not src.exists():
            continue
        try:
            shutil.copy2(src, install_dir / name)
        except Exception:
            pass


def _seed_user_preferences_defaults(*, volume_multiplier: float) -> None:
    """Seed per-user preferences.json with installer defaults.

    This is intentionally only called on *new install*, not upgrade/reinstall,
    so an existing user's preferences remain unchanged.
    """

    try:
        data_root = Path(user_data_dir(APP_NAME, APP_AUTHOR)).resolve()
        prefs_path = data_root / "preferences.json"
        prefs_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "playback_volume": float(volume_multiplier),
        }

        # Atomic-ish write to avoid leaving a truncated file if the installer is
        # interrupted.
        tmp = prefs_path.with_suffix(prefs_path.suffix + f".tmp.{uuid.uuid4().hex}")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(prefs_path)

        logger.info("Seeded user preferences at %s", prefs_path)
    except Exception:
        # Best-effort: the app can still run with built-in defaults.
        logger.exception("Failed seeding user preferences")


def install_new(
    identity: InstallerIdentity,
    opts: InstallOptions,
    *,
    progress=None,
    cancel_event=None,
) -> None:  # noqa: ANN001
    target_dir = opts.target_dir.resolve()

    migrate_legacy_appdata_dirs()

    # Stage in the target's parent directory so we can do an atomic rename when
    # target lives on a non-system drive.
    staging_dir = target_dir.parent / f".clearbudget_staging.install.{uuid.uuid4().hex}"
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)

    try:
        _extract_payload_to(staging_dir, progress=progress, cancel_event=cancel_event)
        _progress(progress, pct=45, message="Installing...")

        _check_cancel(cancel_event)
        _swap_in_bundle(staging_dir, target_dir)

        # Make sure icon assets are available next to the installed exe.
        _deploy_runtime_icon_assets(install_dir=target_dir)

        # Seed user preferences so a true "first run" starts with the intended
        # default volume. This writes to the per-user data directory (not the
        # install directory).
        _seed_user_preferences_defaults(volume_multiplier=0.25)

        _progress(progress, pct=75, message="Registering uninstall entry...")
        _check_cancel(cancel_event)
        logger.info("Registering uninstall entry for %s", target_dir)
        installer_copy = _copy_self_to_install(identity, target_dir)
        _register_uninstall(
            identity,
            install_dir=target_dir,
            installer_copy=installer_copy,
            shortcut_desktop=opts.create_desktop_shortcut,
            shortcut_start_menu=opts.create_start_menu_shortcut,
        )

        _progress(progress, pct=90, message="Creating shortcuts...")
        _check_cancel(cancel_event)
        logger.info("Applying shortcuts")
        _apply_shortcuts(identity, target_dir, opts)

        # Now the new install is fully in place, remove the stale, unreferenced
        # install directory left behind by the app rename (if any).
        cleanup_orphaned_legacy_install(target_dir)

        _progress(progress, pct=100, message="Completed")
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


def upgrade_or_reinstall(
    identity: InstallerIdentity,
    *,
    current_install_dir: Path,
    opts: InstallOptions,
    progress=None,
    cancel_event=None,
) -> None:
    current_install_dir = current_install_dir.resolve()
    target_dir = opts.target_dir.resolve()

    migrate_legacy_appdata_dirs()

    exe = current_install_dir / "ClearBudget.exe"
    if exe.exists() and is_app_running(exe):
        raise AppRunningError("Clear Budget is currently running")

    logger.info(
        "Upgrade/reinstall: current=%s target=%s", current_install_dir, target_dir
    )

    staging_dir = target_dir.parent / f".clearbudget_staging.upgrade.{uuid.uuid4().hex}"
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)

    try:
        _extract_payload_to(staging_dir, progress=progress, cancel_event=cancel_event)

        _progress(progress, pct=45, message="Replacing application files...")

        _check_cancel(cancel_event)

        if target_dir == current_install_dir:
            _swap_in_bundle(staging_dir, target_dir)
        else:
            # Install to new location, then delete old.
            _swap_in_bundle(staging_dir, target_dir)

            try:
                shutil.rmtree(current_install_dir, ignore_errors=True)
            except Exception:
                pass

        # Ensure icon assets are present for the active install location.
        _deploy_runtime_icon_assets(install_dir=target_dir)

        _progress(progress, pct=75, message="Registering uninstall entry...")
        _check_cancel(cancel_event)
        logger.info("Registering uninstall entry for %s", target_dir)
        installer_copy = _copy_self_to_install(identity, target_dir)
        _register_uninstall(
            identity,
            install_dir=target_dir,
            installer_copy=installer_copy,
            shortcut_desktop=opts.create_desktop_shortcut,
            shortcut_start_menu=opts.create_start_menu_shortcut,
        )

        _progress(progress, pct=90, message="Updating shortcuts...")
        _check_cancel(cancel_event)
        logger.info("Applying shortcuts")
        _apply_shortcuts(identity, target_dir, opts)

        # Now the new install is fully in place, remove the stale, unreferenced
        # install directory left behind by the app rename (if any).
        cleanup_orphaned_legacy_install(target_dir)

        _progress(progress, pct=100, message="Completed")
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


def _apply_shortcuts(
    identity: InstallerIdentity, install_dir: Path, opts: InstallOptions
) -> None:
    exe = install_dir / "ClearBudget.exe"
    sp = get_shortcut_paths(identity)

    if opts.create_desktop_shortcut:
        create_shortcut(exe, sp.desktop_lnk, working_dir=install_dir)
    else:
        # If user unchecks during reinstall/upgrade, remove it.
        try:
            sp.desktop_lnk.unlink(missing_ok=True)
        except Exception:
            pass

    if opts.create_start_menu_shortcut:
        create_shortcut(exe, sp.start_menu_lnk, working_dir=install_dir)
    else:
        try:
            sp.start_menu_lnk.unlink(missing_ok=True)
        except Exception:
            pass
