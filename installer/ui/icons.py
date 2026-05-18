"""Qt icon helpers for installer UI."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtGui import QIcon


def build_installer_window_icon(*, project_root: Path) -> QIcon:
    """Load installer window icon from actual branded icon files."""
    from PySide6.QtGui import QIcon

    brand_path = _find_brand_icon_path(project_root=project_root)
    if brand_path is not None:
        return QIcon(str(brand_path))

    return QIcon()


def _find_brand_icon_path(*, project_root: Path) -> Path | None:
    """Find a branded icon file for the installer runtime window icon.

    Prefer PNGs (we have a known-good multi-size PNG set), then fall back to the
    `.ico` if needed.
    """

    filenames = [
        "clearbudget_256.png",
        "clearbudget_128.png",
        "clearbudget_64.png",
        "clearbudget_48.png",
        "clearbudget.ico",
    ]

    roots: list[Path] = []

    # In a frozen PyInstaller build, bundled files live under sys._MEIPASS.
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(Path(meipass))
    except Exception:
        pass

    roots.append(project_root)

    # Next to exe.
    try:
        roots.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass

    # CWD as a final fallback.
    try:
        roots.append(Path.cwd())
    except Exception:
        pass

    for root in roots:
        for name in filenames:
            p = root / name
            try:
                if p.exists() and p.is_file():
                    return p
            except Exception:
                continue

    return None


def set_windows_app_user_model_id(app_id: str) -> None:
    """Set the Windows AppUserModelID for correct taskbar grouping/icon.

    This is a best-effort helper; it no-ops on non-Windows.
    """

    if os.name != "nt":
        return

    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        return
