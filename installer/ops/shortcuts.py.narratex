"""Create/remove per-user shortcuts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from installer.constants import InstallerIdentity
from installer.ops.errors import InstallerOperationError
from voice_reader.version import APP_APPUSERMODELID


def _default_icon_location_for(target_exe: Path) -> str:
    """Choose the best icon source for a shortcut.

    Prefer `narratex.ico` next to the exe (deployed by the installer) so the
    shortcut uses the branded icon even if the exe's embedded icon changes.
    """

    try:
        ico = target_exe.resolve().parent / "narratex.ico"
        if ico.exists() and ico.is_file():
            return str(ico)
    except Exception:
        pass

    return str(target_exe)


@dataclass(frozen=True, slots=True)
class ShortcutPaths:
    desktop_lnk: Path
    start_menu_lnk: Path


def _require_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("Shortcuts are supported on Windows only")


def get_shortcut_paths(identity: InstallerIdentity) -> ShortcutPaths:
    _require_windows()

    # Per-user Desktop.
    desktop_dir = Path(os.path.join(os.path.expanduser("~"), "Desktop"))

    # Per-user Start Menu Programs.
    appdata = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    programs_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"

    start_menu_folder = programs_dir / identity.start_menu_folder

    return ShortcutPaths(
        desktop_lnk=desktop_dir / f"{identity.shortcut_name}.lnk",
        start_menu_lnk=start_menu_folder / f"{identity.shortcut_name}.lnk",
    )


def create_shortcut(
    target_exe: Path, shortcut_path: Path, *, working_dir: Path | None = None
) -> None:
    _require_windows()
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)

    # Create the shortcut directly via the Shell Link COM API.
    #
    # Important: do NOT create the shortcut via WScript.Shell and then attempt to
    # stamp System.AppUserModel.ID afterwards via wrapper conversion.
    #
    # Taskbar identity must be deterministic for installed launches.
    pythoncom = None
    com_initialized = False
    try:
        import pythoncom as _pythoncom  # type: ignore  # noqa: WPS433
        from win32com.propsys import propsys  # type: ignore  # noqa: WPS433
        from win32com.shell import shell  # type: ignore  # noqa: WPS433

        pythoncom = _pythoncom

        pythoncom.CoInitialize()
        com_initialized = True

        link = pythoncom.CoCreateInstance(
            shell.CLSID_ShellLink,
            None,
            pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_IShellLink,
        )

        link.SetPath(str(target_exe))
        if working_dir is not None:
            link.SetWorkingDirectory(str(working_dir))

        link.SetIconLocation(_default_icon_location_for(target_exe), 0)

        if not APP_APPUSERMODELID:
            raise InstallerOperationError("APP_APPUSERMODELID is empty")

        store = link.QueryInterface(propsys.IID_IPropertyStore)
        key = propsys.PSGetPropertyKeyFromName("System.AppUserModel.ID")
        pv = propsys.PROPVARIANTType(APP_APPUSERMODELID)
        store.SetValue(key, pv)
        store.Commit()

        persist = link.QueryInterface(pythoncom.IID_IPersistFile)
        persist.Save(str(shortcut_path), 0)
    except InstallerOperationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise InstallerOperationError(
            f"Failed to create shortcut '{shortcut_path}' -> '{target_exe}': {exc!r}"
        ) from exc
    finally:
        try:
            if pythoncom is not None and com_initialized:
                pythoncom.CoUninitialize()
        except Exception:
            # Nothing sensible to do here; shortcut creation already failed/succeeded.
            pass


def remove_shortcut(shortcut_path: Path) -> None:
    try:
        shortcut_path.unlink(missing_ok=True)
    except Exception:
        # Best effort.
        return

    # Remove parent folder if empty (Start Menu subfolder).
    try:
        if shortcut_path.parent.exists() and not any(shortcut_path.parent.iterdir()):
            shortcut_path.parent.rmdir()
    except Exception:
        return
