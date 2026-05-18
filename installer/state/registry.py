"""Windows uninstall registry integration (HKCU).

This is the source of truth for installed state and makes ClearBudget appear in
Settings > Apps.
"""

from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True, slots=True)
class UninstallEntry:
    display_name: str
    display_version: str
    install_location: Path
    uninstall_string: str

    display_icon: Optional[str] = None
    publisher: Optional[str] = None

    shortcut_desktop: Optional[bool] = None
    shortcut_start_menu: Optional[bool] = None
    installer_path: Optional[str] = None


def _require_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("Registry operations are supported on Windows only")


def read_uninstall_entry(uninstall_key: str) -> Optional[UninstallEntry]:
    _require_windows()

    import winreg  # noqa: WPS433 (stdlib, windows-only)

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uninstall_key) as k:

            def _q(name: str) -> Optional[str]:
                try:
                    return str(winreg.QueryValueEx(k, name)[0])
                except OSError:
                    return None

            display_name = _q("DisplayName") or ""
            display_version = _q("DisplayVersion") or ""
            install_location_raw = _q("InstallLocation")
            uninstall_string = _q("UninstallString") or ""

            if not (display_name and install_location_raw and uninstall_string):
                return None

            install_location = Path(str(install_location_raw)).expanduser()
            # Guard against missing/invalid values that would otherwise become
            # Path('.') and be truthy.
            if not install_location.is_absolute():
                return None

            return UninstallEntry(
                display_name=display_name,
                display_version=display_version,
                install_location=install_location,
                uninstall_string=uninstall_string,
                display_icon=_q("DisplayIcon"),
                publisher=_q("Publisher"),
                shortcut_desktop=_parse_bool(_q("ShortcutDesktop")),
                shortcut_start_menu=_parse_bool(_q("ShortcutStartMenu")),
                installer_path=_q("InstallerPath"),
            )
    except FileNotFoundError:
        return None


def write_uninstall_entry(
    uninstall_key: str,
    *,
    display_name: str,
    display_version: str,
    install_location: Path,
    uninstall_string: str,
    display_icon: Optional[str] = None,
    publisher: Optional[str] = None,
    shortcut_desktop: Optional[bool] = None,
    shortcut_start_menu: Optional[bool] = None,
    installer_path: Optional[str] = None,
) -> None:
    _require_windows()

    import winreg  # noqa: WPS433 (stdlib, windows-only)

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall_key) as k:
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, display_name)
        winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, display_version)
        winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, str(install_location))
        winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ, uninstall_string)

        if display_icon:
            winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, display_icon)
        if publisher:
            winreg.SetValueEx(k, "Publisher", 0, winreg.REG_SZ, publisher)

        today = _dt.date.today().strftime("%Y%m%d")
        winreg.SetValueEx(k, "InstallDate", 0, winreg.REG_SZ, today)

        # Avoid Windows showing Modify/Repair buttons; our installer handles this.
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)

        if shortcut_desktop is not None:
            winreg.SetValueEx(
                k, "ShortcutDesktop", 0, winreg.REG_SZ, "1" if shortcut_desktop else "0"
            )
        if shortcut_start_menu is not None:
            winreg.SetValueEx(
                k,
                "ShortcutStartMenu",
                0,
                winreg.REG_SZ,
                "1" if shortcut_start_menu else "0",
            )
        if installer_path:
            winreg.SetValueEx(k, "InstallerPath", 0, winreg.REG_SZ, installer_path)


def delete_uninstall_entry(uninstall_key: str) -> None:
    _require_windows()

    import winreg  # noqa: WPS433 (stdlib, windows-only)

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, uninstall_key)
    except FileNotFoundError:
        return
    except OSError:
        # Key might contain values but no subkeys; DeleteKey should still work.
        # If it fails for any other reason, rethrow.
        raise


def try_read_install_location(uninstall_key: str) -> Optional[Path]:
    """Best-effort read of InstallLocation even if other fields are missing."""

    _require_windows()

    import winreg  # noqa: WPS433 (stdlib, windows-only)

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uninstall_key) as k:
            try:
                v = str(winreg.QueryValueEx(k, "InstallLocation")[0])
                p = Path(v)
                return p
            except OSError:
                return None
    except FileNotFoundError:
        return None


def _parse_bool(v: Optional[str]) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return None
