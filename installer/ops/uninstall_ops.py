"""Uninstall: remove the shortcuts, the registration and then the files.

The registration is removed before the files, so a removal that is interrupted
part way leaves an orphaned directory rather than an entry in "Apps & features"
pointing at nothing.

Uninstall does NOT touch user data, by decision. It removes the program and
leaves the user's data directory alone, so accounts, every user's budget and
the saved theme survive an uninstall and reinstalling picks up where the user
left off. There is nothing to opt into: an option to delete every budget on the
machine is irreversible; an installer is the wrong place to offer it. What
stood here once deleted two platformdirs directories this app has never written
to, inherited from the installer this one was rebranded from; it presented
itself as removing user data while removing none.

British spelling is used in comments.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from installer.constants import InstallerIdentity
from installer.ops.commands import CommandRunner
from installer.ops.errors import AppRunningError, InstallerOperationError
from installer.ops.progress import (
    COMPLETE_PCT,
    READ_METADATA_MESSAGE,
    READ_METADATA_PCT,
    REMOVE_FILES_MESSAGE,
    REMOVE_FILES_PCT,
    REMOVE_REGISTRY_MESSAGE,
    REMOVE_REGISTRY_PCT,
    REMOVE_SHORTCUTS_MESSAGE,
    REMOVE_SHORTCUTS_PCT,
    UNINSTALL_DONE_MESSAGE,
    ProgressCallback,
    report,
)
from installer.ops.registration import installed_exe
from installer.ops.removal import remove_install_dir
from installer.ops.running_app import ProcessController, is_app_running
from installer.ops.shortcuts import (
    get_shortcut_paths,
    remove_shortcut,
    remove_taskbar_pin,
)
from installer.ops.staging import check_cancel
from installer.state.registry import (
    delete_uninstall_entry,
    read_uninstall_entry,
    try_read_install_location,
)

WINDOWS_ONLY_MESSAGE = "Uninstall is Windows-only"
NOT_INSTALLED_MESSAGE = "Clear Budget is not detected as installed for this user"
APP_RUNNING_MESSAGE = "Clear Budget is currently running"

_WINDOWS_OS_NAME = "nt"


@dataclass(frozen=True, slots=True)
class UninstallOptions:
    """Options for an uninstall.

    Empty on purpose: the one option that used to live here, `remove_user_data`,
    is gone with the behaviour it controlled. The type is kept because the
    uninstall entry points take it and a future option (keeping shortcuts, say)
    would land here rather than growing another parameter.
    """


def _locate_install(identity: InstallerIdentity) -> tuple[Path, object]:
    """Return the install directory and the registry entry it came from."""
    entry = read_uninstall_entry(identity.uninstall_key)
    install_dir = (
        entry.install_location
        if entry is not None
        else try_read_install_location(identity.uninstall_key)
    )
    if install_dir is None:
        raise InstallerOperationError(NOT_INSTALLED_MESSAGE)
    return install_dir.resolve(), entry


def uninstall(
    identity: InstallerIdentity,
    opts: UninstallOptions,
    *,
    progress: ProgressCallback | None = None,
    cancel_event=None,
    controller: ProcessController | None = None,
    runner: CommandRunner | None = None,
) -> None:
    """Remove the shortcuts, the registrations and then the install directory."""
    del opts

    if os.name != _WINDOWS_OS_NAME:
        raise InstallerOperationError(WINDOWS_ONLY_MESSAGE)

    check_cancel(cancel_event)
    report(progress, READ_METADATA_PCT, READ_METADATA_MESSAGE)
    install_dir, entry = _locate_install(identity)

    exe = installed_exe(install_dir)
    if exe.exists() and is_app_running(exe, controller):
        raise AppRunningError(APP_RUNNING_MESSAGE)

    report(progress, REMOVE_SHORTCUTS_PCT, REMOVE_SHORTCUTS_MESSAGE)
    _remove_shortcuts(identity, entry)

    report(progress, REMOVE_REGISTRY_PCT, REMOVE_REGISTRY_MESSAGE)
    _delete_registration(identity)

    report(progress, REMOVE_FILES_PCT, REMOVE_FILES_MESSAGE)
    if install_dir.exists():
        remove_install_dir(install_dir, runner)

    report(progress, COMPLETE_PCT, UNINSTALL_DONE_MESSAGE)


def _remove_shortcuts(identity: InstallerIdentity, entry) -> None:
    """Remove whichever shortcuts the installation recorded, plus any pin.

    An entry that cannot be read leaves both shortcut flags unknown, so both
    are removed: an uninstall must not leave a launchable shortcut behind.
    """
    sp = get_shortcut_paths(identity)
    if entry is None or entry.shortcut_desktop is not False:
        remove_shortcut(sp.desktop_lnk)
    if entry is None or entry.shortcut_start_menu is not False:
        remove_shortcut(sp.start_menu_lnk)

    # The taskbar pin is user-created and not tracked by the persisted shortcut
    # flags, so it is always attempted.
    remove_taskbar_pin(sp.taskbar_lnk)


def _delete_registration(identity: InstallerIdentity) -> None:
    """Remove the Uninstall key, tolerating a key that has already gone.

    Best effort: the files are about to be removed either way; refusing to
    uninstall because the registration was already deleted by hand would leave
    the user with no way to remove the program at all.
    """
    try:
        delete_uninstall_entry(identity.uninstall_key)
    except OSError:
        return


def uninstall_with_feedback(
    identity: InstallerIdentity,
    opts: UninstallOptions,
    *,
    progress=None,
    cancel_event=None,
    controller: ProcessController | None = None,
    runner: CommandRunner | None = None,
) -> None:
    """Run the uninstall, reporting each phase to the caller's progress bar."""
    uninstall(
        identity,
        opts,
        progress=progress,
        cancel_event=cancel_event,
        controller=controller,
        runner=runner,
    )
