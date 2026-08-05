"""Creating and removing the per-user shortcuts.

Shortcuts are written through the Shell Link COM interface directly, not
through WScript.Shell with the taskbar identity stamped on afterwards. The
identity has to be set on the link before it is saved; otherwise Windows groups an
installed launch under a different taskbar item from a pinned one.

British spelling is used in comments.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from clear_budget.version import APP_APPUSERMODELID
from installer.constants import (
    APP_ICO_NAME,
    DESKTOP_DIR_NAME,
    ENV_APPDATA,
    ROAMING_APPDATA_FALLBACK,
    SHORTCUT_EXT,
    START_MENU_SUBPATH,
    TASKBAR_PIN_SUBPATH,
    InstallerIdentity,
)
from installer.ops.errors import InstallerOperationError

_WINDOWS_OS_NAME = "nt"
_AUMID_PROPERTY = "System.AppUserModel.ID"
_ICON_INDEX = 0
_SAVE_REMEMBER_FLAG = 0

WINDOWS_ONLY_MESSAGE = "Shortcuts are supported on Windows only"
EMPTY_AUMID_MESSAGE = "APP_APPUSERMODELID is empty"


def _require_windows() -> None:
    if os.name != _WINDOWS_OS_NAME:
        raise RuntimeError(WINDOWS_ONLY_MESSAGE)


def _roaming_appdata() -> Path:
    """Return %APPDATA%, falling back to its conventional location."""
    appdata = os.getenv(ENV_APPDATA)
    if appdata:
        return Path(appdata)
    return Path.home().joinpath(*ROAMING_APPDATA_FALLBACK)


def icon_location_for(target_exe: Path) -> str:
    """Choose the icon source for a shortcut.

    Prefer the multi-resolution ICO the installer deploys beside the
    executable, so the shortcut keeps the branded icon even if the executable's
    embedded icon changes.
    """
    ico = target_exe.parent / APP_ICO_NAME
    if ico.is_file():
        return str(ico.resolve())
    return str(target_exe)


@dataclass(frozen=True, slots=True)
class ShortcutPaths:
    desktop_lnk: Path
    start_menu_lnk: Path
    taskbar_lnk: Path


def get_shortcut_paths(identity: InstallerIdentity) -> ShortcutPaths:
    """Return every per-user shortcut location, all under the user's profile."""
    _require_windows()

    desktop_dir = Path(os.path.expanduser("~")) / DESKTOP_DIR_NAME
    appdata = _roaming_appdata()
    start_menu_folder = (
        appdata.joinpath(*START_MENU_SUBPATH) / identity.start_menu_folder
    )
    taskbar_dir = appdata.joinpath(*TASKBAR_PIN_SUBPATH)

    link_name = f"{identity.shortcut_name}{SHORTCUT_EXT}"
    return ShortcutPaths(
        desktop_lnk=desktop_dir / link_name,
        start_menu_lnk=start_menu_folder / link_name,
        taskbar_lnk=taskbar_dir / link_name,
    )


def _write_shell_link(
    target_exe: Path, shortcut_path: Path, working_dir: Path | None
) -> None:
    """Create one shortcut through the Shell Link COM interface."""
    import pythoncom
    from win32com.propsys import propsys
    from win32com.shell import shell

    pythoncom.CoInitialize()
    try:
        link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink,
            None,
            pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_IShellLink,
        )
        link.SetPath(str(target_exe))
        if working_dir is not None:
            link.SetWorkingDirectory(str(working_dir))
        link.SetIconLocation(icon_location_for(target_exe), _ICON_INDEX)

        store = link.QueryInterface(propsys.IID_IPropertyStore)
        key = propsys.PSGetPropertyKeyFromName(_AUMID_PROPERTY)
        store.SetValue(key, propsys.PROPVARIANTType(APP_APPUSERMODELID))
        store.Commit()

        link.QueryInterface(pythoncom.IID_IPersistFile).Save(
            str(shortcut_path), _SAVE_REMEMBER_FLAG
        )
    finally:
        pythoncom.CoUninitialize()


def create_shortcut(
    target_exe: Path, shortcut_path: Path, *, working_dir: Path | None = None
) -> None:
    """Write a shortcut to the installed executable, carrying the app icon."""
    _require_windows()
    if not APP_APPUSERMODELID:
        raise InstallerOperationError(EMPTY_AUMID_MESSAGE)

    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write_shell_link(target_exe, shortcut_path, working_dir)
    except Exception as exc:
        # Deliberately broad: the COM layer raises pywintypes.com_error, which
        # is not an OSError; an absent pywin32 raises ImportError. Both mean
        # the same thing to the caller, so both are reported as one failure.
        raise InstallerOperationError(
            f"Failed to create shortcut '{shortcut_path}' -> '{target_exe}': {exc!r}"
        ) from exc


def remove_shortcut(shortcut_path: Path) -> None:
    """Delete a shortcut; also its Start Menu folder when that is left empty.

    Best effort throughout: a shortcut that cannot be removed is a leftover
    icon, not a reason to fail an uninstall that has already removed the
    program the shortcut points at.
    """
    try:
        shortcut_path.unlink(missing_ok=True)
    except OSError:
        return

    try:
        if shortcut_path.parent.exists() and not any(shortcut_path.parent.iterdir()):
            shortcut_path.parent.rmdir()
    except OSError:
        return


def remove_taskbar_pin(shortcut_path: Path) -> None:
    """Remove a taskbar pin shortcut file, best effort.

    Only the .lnk is deleted; the shared "User Pinned\\TaskBar" folder is left
    in place because Windows manages it. The live taskbar icon may persist
    until Explorer restarts or the user next signs in; it no longer
    launches the removed app.
    """
    try:
        shortcut_path.unlink(missing_ok=True)
    except OSError:
        return
