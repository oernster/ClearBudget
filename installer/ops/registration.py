"""Making a deployed bundle into an installed program.

Three things turn a directory of files into an installation Windows knows
about: a copy of the setup program that "Apps & features" can re-run to remove
it, the icon assets the shortcuts and the Apps list point at, then the HKCU
Uninstall key itself. British spelling is used in comments.
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

from clear_budget.shared.resources import find_app_icon_path
from clear_budget.version import APP_AUTHOR, APP_NAME, __version__
from installer.constants import (
    APP_EXE_NAME,
    APP_ICO_NAME,
    APP_ICO_NAMES,
    APP_ICON_PNG_NAMES,
    InstallerIdentity,
)
from installer.shared.resource_path import bundled_data_root
from installer.state.registry import write_uninstall_entry

logger = logging.getLogger("installer.install")

UNINSTALL_FLAG = "--uninstall"


def installed_exe(install_dir: Path) -> Path:
    """Return the application executable inside an install directory."""
    return install_dir / APP_EXE_NAME


def copy_self_to_install(identity: InstallerIdentity, install_dir: Path) -> Path:
    """Copy the setup program under the install root, to act as the uninstaller."""
    install_dir = install_dir.resolve()
    dst = identity.installer_exe_path(install_dir)
    dst.parent.mkdir(parents=True, exist_ok=True)

    src = Path(sys.executable).resolve()
    logger.info("Copying installer from %s to %s", src, dst)
    shutil.copy2(src, dst)
    return dst


def display_icon_for(install_dir: Path) -> str:
    """Return the Apps-list icon: the multi-resolution ICO, else the executable."""
    for ico_name in APP_ICO_NAMES:
        ico_path = install_dir / ico_name
        if ico_path.exists():
            return str(ico_path)
    return str(installed_exe(install_dir))


def register_uninstall(
    identity: InstallerIdentity,
    *,
    install_dir: Path,
    installer_copy: Path,
    shortcut_desktop: bool,
    shortcut_start_menu: bool,
) -> None:
    """Record the installation so it appears in Apps and features."""
    write_uninstall_entry(
        identity.uninstall_key,
        display_name=APP_NAME,
        display_version=__version__,
        install_location=install_dir,
        uninstall_string=f'"{installer_copy}" {UNINSTALL_FLAG}',
        display_icon=display_icon_for(install_dir),
        publisher=APP_AUTHOR,
        shortcut_desktop=shortcut_desktop,
        shortcut_start_menu=shortcut_start_menu,
        installer_path=str(installer_copy),
    )


def deploy_runtime_icon_assets(*, install_dir: Path) -> None:
    """Deploy the icon assets next to the installed executable.

    The multi-resolution ICO drives the shortcuts and the Apps list; the PNGs
    are the Qt runtime fallback for the window and taskbar icon when the ICO
    image plugin is unavailable in the frozen build. Both are best effort: an
    icon that cannot be copied leaves the executable's own embedded icon in
    use, which is a cosmetic loss and not a reason to fail an install whose
    files are already down.
    """
    project_root = bundled_data_root()

    ico = find_app_icon_path(project_root=project_root)
    if ico is not None:
        _copy_asset(ico, install_dir / APP_ICO_NAME)

    for name in APP_ICON_PNG_NAMES:
        src = project_root / name
        if src.exists():
            _copy_asset(src, install_dir / name)


def _copy_asset(src: Path, dst: Path) -> None:
    """Copy one icon asset, logging and continuing when it cannot be copied."""
    try:
        shutil.copy2(src, dst)
    except OSError:
        logger.exception("Failed deploying icon asset %s", src)
