"""Install, upgrade and reinstall.

All three are the same sequence: stage the payload beside the target, swap it
into place, deploy the icon assets, register the uninstaller, then apply the
shortcut choices. They differ only in what they do with a previous install.

Every one of them refuses to run while the application holds its own files
open, a fresh install included: installing into a directory that already holds
a running executable would try to replace files Windows has locked, which
fails part way through and leaves a half-written bundle. The caller offers to
close the application rather than only reporting that it is open.

User settings live outside the install directory, so nothing here touches them.
British spelling is used in comments.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from installer.constants import APP_INTERNAL_DIR_NAME, InstallerIdentity
from installer.ops.errors import AppRunningError, InstallerOperationError
from installer.ops.legacy import migrate_legacy_appdata_dirs
from installer.ops.payload import extract_archive, payload_zip_path
from installer.ops.progress import (
    CLEANUP_MESSAGE,
    CLEANUP_PCT,
    COMPLETE_PCT,
    DONE_MESSAGE,
    ICON_ASSETS_MESSAGE,
    ICON_ASSETS_PCT,
    REGISTER_MESSAGE,
    REGISTER_PCT,
    SHORTCUTS_MESSAGE,
    SHORTCUTS_PCT,
    SWAP_MESSAGE,
    SWAP_PCT,
    UPDATE_SHORTCUTS_MESSAGE,
    ProgressCallback,
    report,
)
from installer.ops.registration import (
    copy_self_to_install,
    deploy_runtime_icon_assets,
    installed_exe,
    register_uninstall,
)
from installer.ops.running_app import ProcessController, is_app_running
from installer.ops.shortcuts import create_shortcut, get_shortcut_paths, remove_shortcut
from installer.ops.staging import check_cancel, staging_dir_for, swap_in_bundle

logger = logging.getLogger("installer.install")

APP_RUNNING_MESSAGE = "Clear Budget is currently running"

_INSTALL_PURPOSE = "install"
_UPGRADE_PURPOSE = "upgrade"


@dataclass(frozen=True, slots=True)
class InstallOptions:
    target_dir: Path
    create_desktop_shortcut: bool
    create_start_menu_shortcut: bool


def guard_not_running(
    install_dir: Path,
    controller: ProcessController | None = None,
) -> None:
    """Refuse to proceed while the application holds its own files open."""
    exe = installed_exe(install_dir)
    if exe.exists() and is_app_running(exe, controller):
        raise AppRunningError(APP_RUNNING_MESSAGE)


def _extract_payload_to(
    staging_dir: Path,
    *,
    progress: ProgressCallback | None = None,
    cancel_event=None,
) -> None:
    """Extract the bundled payload into the staging directory and check it."""
    check_cancel(cancel_event)
    logger.info("Extracting payload to %s", staging_dir)
    extract_archive(
        payload_zip_path(),
        staging_dir,
        progress=progress,
        cancel_check=lambda: check_cancel(cancel_event),
    )
    check_cancel(cancel_event)

    exe = installed_exe(staging_dir)
    internal = staging_dir / APP_INTERNAL_DIR_NAME
    if not exe.exists() or not internal.exists():
        raise InstallerOperationError(
            f"Payload is missing {exe.name} or {APP_INTERNAL_DIR_NAME}/"
        )


def _deploy_and_register(
    identity: InstallerIdentity,
    staging_dir: Path,
    target_dir: Path,
    opts: InstallOptions,
    *,
    progress: ProgressCallback | None,
    cancel_event,
) -> None:
    """Swap the staged bundle into place and make it an installed program."""
    report(progress, SWAP_PCT, SWAP_MESSAGE)
    check_cancel(cancel_event)
    swap_in_bundle(staging_dir, target_dir)

    report(progress, ICON_ASSETS_PCT, ICON_ASSETS_MESSAGE)
    deploy_runtime_icon_assets(install_dir=target_dir)

    report(progress, REGISTER_PCT, REGISTER_MESSAGE)
    check_cancel(cancel_event)
    logger.info("Registering uninstall entry for %s", target_dir)
    installer_copy = copy_self_to_install(identity, target_dir)
    register_uninstall(
        identity,
        install_dir=target_dir,
        installer_copy=installer_copy,
        shortcut_desktop=opts.create_desktop_shortcut,
        shortcut_start_menu=opts.create_start_menu_shortcut,
    )


def _finish(
    identity: InstallerIdentity,
    target_dir: Path,
    opts: InstallOptions,
    *,
    progress: ProgressCallback | None,
    cancel_event,
    shortcuts_message: str,
) -> None:
    """Apply the shortcut choices, clear the legacy install and report done."""
    report(progress, SHORTCUTS_PCT, shortcuts_message)
    check_cancel(cancel_event)
    logger.info("Applying shortcuts")
    apply_shortcuts(identity, target_dir, opts)

    # No stale-install cleanup any more: the helper that removed the
    # pre-rename install directory deleted the app's DATA directory once the
    # data moved to that path. The tidy-up is gone for good; see
    # installer/ops/legacy.py for the account.
    report(progress, CLEANUP_PCT, CLEANUP_MESSAGE)

    report(progress, COMPLETE_PCT, DONE_MESSAGE)


def install_new(
    identity: InstallerIdentity,
    opts: InstallOptions,
    *,
    progress=None,
    cancel_event=None,
    controller: ProcessController | None = None,
) -> None:
    target_dir = opts.target_dir.resolve()

    guard_not_running(target_dir, controller)
    migrate_legacy_appdata_dirs()

    staging_dir = staging_dir_for(target_dir, _INSTALL_PURPOSE)
    try:
        _extract_payload_to(staging_dir, progress=progress, cancel_event=cancel_event)
        _deploy_and_register(
            identity,
            staging_dir,
            target_dir,
            opts,
            progress=progress,
            cancel_event=cancel_event,
        )
        _finish(
            identity,
            target_dir,
            opts,
            progress=progress,
            cancel_event=cancel_event,
            shortcuts_message=SHORTCUTS_MESSAGE,
        )
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
    controller: ProcessController | None = None,
) -> None:
    current_install_dir = current_install_dir.resolve()
    target_dir = opts.target_dir.resolve()

    guard_not_running(current_install_dir, controller)
    migrate_legacy_appdata_dirs()

    logger.info(
        "Upgrade/reinstall: current=%s target=%s", current_install_dir, target_dir
    )

    staging_dir = staging_dir_for(target_dir, _UPGRADE_PURPOSE)
    try:
        _extract_payload_to(staging_dir, progress=progress, cancel_event=cancel_event)
        _deploy_and_register(
            identity,
            staging_dir,
            target_dir,
            opts,
            progress=progress,
            cancel_event=cancel_event,
        )
        if target_dir != current_install_dir:
            # Installed to a new location, so the old one is now unreferenced.
            shutil.rmtree(current_install_dir, ignore_errors=True)
        _finish(
            identity,
            target_dir,
            opts,
            progress=progress,
            cancel_event=cancel_event,
            shortcuts_message=UPDATE_SHORTCUTS_MESSAGE,
        )
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


def apply_shortcuts(
    identity: InstallerIdentity, install_dir: Path, opts: InstallOptions
) -> None:
    """Create or remove the shortcuts so they match the chosen options."""
    exe = installed_exe(install_dir)
    sp = get_shortcut_paths(identity)

    if opts.create_desktop_shortcut:
        create_shortcut(exe, sp.desktop_lnk, working_dir=install_dir)
    else:
        # The user cleared the box during a reinstall or upgrade, so take it away.
        remove_shortcut(sp.desktop_lnk)

    if opts.create_start_menu_shortcut:
        create_shortcut(exe, sp.start_menu_lnk, working_dir=install_dir)
    else:
        remove_shortcut(sp.start_menu_lnk)
