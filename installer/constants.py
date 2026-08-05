"""Installer constants.

Every name the setup program writes to disk or to the registry is declared
here, so a rename is a single edit and no module carries an inline literal.
British spelling is used in comments.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clear_budget.version import APP_AUTHOR, APP_NAME

UNINSTALL_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ClearBudget"

# --- the deployed application ------------------------------------------------

# The executable the payload deploys, plus the directory PyInstaller puts beside
# it. Both are checked after extraction, so a truncated payload fails loudly.
APP_EXE_NAME = "ClearBudget.exe"
APP_INTERNAL_DIR_NAME = "_internal"

# The multi-resolution icon deployed next to the executable, preferred over the
# executable's embedded icon for shortcuts and for the Apps list entry. Both
# spellings are accepted because older installs wrote the second.
APP_ICO_NAME = "clearbudget.ico"
APP_ICO_NAMES = (APP_ICO_NAME, "ClearBudget.ico")

# PNG sizes deployed beside the executable as a Qt runtime fallback for the
# window and taskbar icon when the ICO plugin is unavailable.
APP_ICON_PNG_NAMES = (
    "clearbudget_16.png",
    "clearbudget_32.png",
    "clearbudget_48.png",
    "clearbudget_64.png",
    "clearbudget_128.png",
    "clearbudget_256.png",
    "clearbudget_512.png",
)

# --- payload layout ----------------------------------------------------------

PAYLOAD_ZIP_RESOURCE = "installer/payload/payload.zip"
MANIFEST_JSON_RESOURCE = "installer/payload/manifest.json"

# --- per-user locations (no administrator rights required) -------------------

ENV_LOCALAPPDATA = "LOCALAPPDATA"
ENV_APPDATA = "APPDATA"
LOCAL_APPDATA_FALLBACK = ("AppData", "Local")
ROAMING_APPDATA_FALLBACK = ("AppData", "Roaming")

# The setup program's own per-user working area: its log and its staging root.
INSTALLER_DIR_NAME = "ClearBudgetInstaller"
INSTALLER_LOG_DIR_NAME = "logs"
INSTALLER_LOG_NAME = "setup.log"

# Staging directories are created beside the install target so the swap into
# place is a same-volume rename. The prefix is deliberately not the app's data
# directory name, which the installer never touches.
STAGING_PREFIX = ".clearbudget_staging"

DESKTOP_DIR_NAME = "Desktop"
START_MENU_SUBPATH = ("Microsoft", "Windows", "Start Menu", "Programs")
TASKBAR_PIN_SUBPATH = (
    "Microsoft",
    "Internet Explorer",
    "Quick Launch",
    "User Pinned",
    "TaskBar",
)
SHORTCUT_EXT = ".lnk"


@dataclass(frozen=True, slots=True)
class InstallerIdentity:
    """Every location the installer reads or writes, as a value.

    Production uses the default set. A test constructs its own with a scratch
    HKCU key and scratch shortcut names, so the behaviour is exercised in full
    without ever touching the user's own registration.
    """

    app_name: str = APP_NAME
    publisher: str = APP_AUTHOR

    uninstall_key: str = UNINSTALL_REG_KEY
    uninstall_key_name: str = "ClearBudget"

    # Location under the install root where we copy the installer exe so it can
    # act as the registered uninstaller.
    installer_subdir: str = "_installer"
    installer_exe_name: str = "ClearBudgetSetup.exe"

    # Start menu folder name under the per-user Programs directory.
    start_menu_folder: str = "ClearBudget"
    shortcut_name: str = "ClearBudget"

    def installer_exe_path(self, install_root: Path) -> Path:
        return install_root / self.installer_subdir / self.installer_exe_name
