"""Turning a requested operation into the call that performs it.

Extracted from [`_main_window_actions`](installer/ui/_main_window_actions.py) to
keep that module inside the 400-line limit. Everything here answers one
question: given the chosen operation and the user's selections, what should be
called, with what, against which installed executable.

British spelling is used in comments.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from installer.ops.errors import InstallerOperationError
from installer.ops.install_ops import InstallOptions, install_new, upgrade_or_reinstall
from installer.ops.registration import installed_exe
from installer.ops.repair_ops import RepairOptions, repair
from installer.ops.uninstall_ops import UninstallOptions, uninstall_with_feedback
from installer.state.model import Operation
from installer.ui._main_window_types import UiSelections

if TYPE_CHECKING:  # pragma: no cover
    from installer.ui.main_window import InstallerMainWindow

# The operations that leave a usable application on disk, so the ones the user
# may be offered a launch of once setup finishes. Repair belongs here for the
# same reason the others do: it puts the executable back, and the "Launch when
# setup finishes" box is on screen while it runs, so leaving it out meant a
# ticked box that did nothing.
LAUNCHABLE_OPS = frozenset(
    {
        Operation.INSTALL,
        Operation.UPGRADE,
        Operation.REINSTALL,
        Operation.REPAIR,
    }
)

NO_INSTALL_MESSAGE = "No existing installation detected"


def read_entry_for(window: InstallerMainWindow):
    """Read the recorded installation through the window's own reader."""
    read_entry = getattr(window, "_read_uninstall_entry", None)
    if read_entry is None:
        from installer.state.registry import read_uninstall_entry as read_entry

    return read_entry(window._identity.uninstall_key)


def target_exe_for(
    window: InstallerMainWindow,
    op: Operation,
    selections: UiSelections,
) -> Path:
    """Return the executable an operation acts on, so it can be closed or run.

    A fresh install has no recorded location, so the executable is the one that
    would sit inside the chosen directory: that is exactly the file a running
    instance would be holding open if the user is installing over themselves.
    """
    if op is not Operation.INSTALL:
        entry = read_entry_for(window)
        if entry is not None:
            return installed_exe(entry.install_location)
    return installed_exe(selections.install_dir)


def operation_callable(
    window: InstallerMainWindow,
    op: Operation,
    selections: UiSelections,
):
    """Return the function that performs ``op`` and the arguments it takes."""
    entry = read_entry_for(window)
    current_install_dir = entry.install_location if entry else None

    install_opts = InstallOptions(
        target_dir=selections.install_dir,
        create_desktop_shortcut=selections.shortcut_desktop,
        create_start_menu_shortcut=selections.shortcut_start_menu,
    )

    if op == Operation.INSTALL:
        return (install_new, {"identity": window._identity, "opts": install_opts})

    if op in {Operation.UPGRADE, Operation.REINSTALL}:
        if current_install_dir is None:
            raise InstallerOperationError(NO_INSTALL_MESSAGE)
        return (
            upgrade_or_reinstall,
            {
                "identity": window._identity,
                "current_install_dir": current_install_dir,
                "opts": install_opts,
            },
        )

    if op == Operation.REPAIR:
        return (
            repair,
            {
                "identity": window._identity,
                "opts": RepairOptions(
                    restore_desktop_shortcut=selections.shortcut_desktop,
                    restore_start_menu_shortcut=selections.shortcut_start_menu,
                ),
            },
        )

    if op == Operation.UNINSTALL:
        return (
            uninstall_with_feedback,
            {"identity": window._identity, "opts": UninstallOptions()},
        )

    raise InstallerOperationError(f"Unsupported operation: {op}")
