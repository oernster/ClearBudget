"""Runtime resource discovery.

For packaging (e.g., PyInstaller onefile), we want a robust way to locate bundled
assets without hard-coding absolute paths.

Every lookup is best-effort: a root that cannot be resolved on this platform is
skipped rather than raised, because a missing icon must never stop the app from
starting.  The guards below are narrow on purpose.  Only filesystem resolution
(`Path.resolve`, `Path.cwd`, `Path.exists`) can realistically fail here, and only
with `OSError`, plus `IndexError` where a parent directory is indexed.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

# Both capitalisation variants are searched: the repo ships `ClearBudget.ico`,
# while some build steps stage it lower-cased.
_ICO_NAMES = ("ClearBudget.ico", "clearbudget.ico")


# The sized PNGs, largest to smallest. Both capitalisations of each are
# searched, for the same reason `_ICO_NAMES` carries both: the REPOSITORY
# ships `ClearBudget_256.png` (that is what `generate_icons.py` writes and what
# git tracks), while several build steps and this module historically staged
# and looked for the lower-cased form. On Windows and on a default macOS
# volume the filesystem hides the difference. On Linux, or on a case-sensitive
# APFS volume, it does not. Searching both is one tuple against a class of bug
# that only ever shows up on someone else's machine.
def _both_cases(stem: str) -> tuple[str, str]:
    """Return ("ClearBudget_x.png", "clearbudget_x.png") for one size stem."""
    return (f"ClearBudget_{stem}.png", f"clearbudget_{stem}.png")


_PNG_SIZES = ("256", "128", "64", "48", "32", "16")

# Preference order for a Qt window icon: native ICO first, then PNGs largest
# to smallest, so Qt gets the best available source when the ICO plugin is
# missing from a frozen build.
_QT_ICON_NAMES = ("clearbudget.ico", "ClearBudget.ico") + tuple(
    name for size in _PNG_SIZES for name in _both_cases(size)
)

_SPLASH_NAMES = _both_cases("256")

# The tab-strip artwork, one file per tab that carries a picture rather than a
# glyph. Looked up by filename through the same roots as every other asset, so
# a frozen build finds them wherever the packaging step staged them.
_TAB_ICON_NAMES = frozenset(("monthlybudget.png", "solvency.png", "creditcards.png"))

# In onedir PyInstaller builds, user-added data files can end up under
# `_internal/` depending on how the `.spec` is generated.
_INTERNAL_DIR = "_internal"


def _meipass_root() -> Path | None:
    """Return the PyInstaller onefile extraction dir, or None outside a bundle."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else None


def _exe_dir() -> Path | None:
    """Return the directory holding the running executable, or None."""
    try:
        return Path(sys.executable).resolve().parent
    except OSError:
        return None


def _repo_root() -> Path | None:
    """Return the repo root for a source checkout, or None.

    Layout: clear_budget/shared/resources.py, so the root is parents[2].
    """
    try:
        return Path(__file__).resolve().parents[2]
    except (OSError, IndexError):
        return None


def _cwd() -> Path | None:
    """Return the current working directory, or None if it is unavailable."""
    try:
        return Path.cwd()
    except OSError:
        return None


def _is_file(path: Path) -> bool:
    """Return True if path is an existing regular file, False if unreadable."""
    try:
        return path.exists() and path.is_file()
    except OSError:
        return False


def _first_existing(candidates: Iterable[Path]) -> Path | None:
    """Return the first candidate that is an existing file, else None."""
    for candidate in candidates:
        if _is_file(candidate):
            return candidate
    return None


def _dedup(paths: Iterable[Path]) -> list[Path]:
    """Drop repeated paths while preserving first-seen order."""
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def find_app_icon_path(*, project_root: Path | None = None) -> Path | None:
    """Locate the ClearBudget `.ico` file for runtime window/taskbar icons."""
    exe_dir = _exe_dir()
    roots = [
        _meipass_root(),
        project_root,
        exe_dir,
        exe_dir / _INTERNAL_DIR if exe_dir is not None else None,
        _repo_root(),
        _cwd(),
    ]
    candidates = [
        root / name for root in roots if root is not None for name in _ICO_NAMES
    ]
    return _first_existing(candidates)


def find_qt_window_icon_path(*, project_root: Path | None = None) -> Path | None:
    """Locate an icon file suitable for Qt window/taskbar icons.

    Prefer `.ico` (native Windows icon), but fall back to a bundled `.png` if
    the Qt ICO plugin is unavailable in the frozen build.
    """
    exe_dir = _exe_dir()
    roots = [
        project_root,
        _meipass_root(),
        exe_dir,
        exe_dir / _INTERNAL_DIR if exe_dir is not None else None,
        _repo_root(),
        _cwd(),
    ]
    candidates = [
        root / name for root in roots if root is not None for name in _QT_ICON_NAMES
    ]
    return _first_existing(candidates)


def find_splash_image_path(*, project_root: Path | None = None) -> Path | None:
    """Locate the ClearBudget splash PNG.

    We prefer a PNG because it is reliably loadable by Qt even when the ICO
    plugin is missing in frozen builds.
    """
    exe_dir = _exe_dir()
    roots = [
        _meipass_root(),
        project_root,
        exe_dir,
        exe_dir / _INTERNAL_DIR if exe_dir is not None else None,
        _repo_root(),
        _cwd(),
    ]
    candidates = [
        root / name for root in roots if root is not None for name in _SPLASH_NAMES
    ]
    return _first_existing(candidates)


def iter_qt_window_icon_candidates(*, project_root: Path | None = None) -> list[Path]:
    """Return icon file candidates (in preference order) for Qt window/taskbar icons.

    This does *not* require Qt and only checks for file existence.

    The caller should still verify the icon is actually loadable by Qt
    (e.g. `.ico` may exist but fail to load if the Qt ICO plugin is missing).
    """
    roots = _dedup(
        root
        for root in (
            project_root,
            _meipass_root(),
            _exe_dir(),
            _repo_root(),
            _cwd(),
        )
        if root is not None
    )
    # `_internal/` variants are searched only after every plain root.
    internal_roots = [root / _INTERNAL_DIR for root in roots]

    return _dedup(
        path
        for root in roots + internal_roots
        for name in _QT_ICON_NAMES
        if _is_file(path := root / name)
    )


def find_tab_icon_path(name: str, *, project_root: Path | None = None) -> Path | None:
    """Locate one of the tab-strip images; None if it is not bundled.

    Restricted to the names this application ships: the caller passes a
    filename and a filename is not something a resource lookup should take on
    trust, however local the call site is today.
    """
    if name not in _TAB_ICON_NAMES:
        return None
    exe_dir = _exe_dir()
    roots = [
        _meipass_root(),
        project_root,
        exe_dir,
        exe_dir / _INTERNAL_DIR if exe_dir is not None else None,
        _repo_root(),
        _cwd(),
    ]
    return _first_existing(root / name for root in roots if root is not None)


def find_logo_png_path(*, project_root: Path | None = None) -> Path | None:
    """Locate the largest bundled PNG of the app icon; None if there is none.

    A PNG specifically, never the `.ico`: the callers paint it into a widget,
    while Qt's ICO support is a plugin a frozen build can be missing (which
    is the whole reason `_QT_ICON_NAMES` lists PNG fallbacks at all).

    This exists so that no caller resolves the icon by counting directory
    levels from its own module. One did, and worked only on Windows: the
    sign-in dialog reached three parents up for a 64px file that the Flatpak
    never stages and that a PyInstaller bundle puts somewhere else entirely,
    so the logo was silently absent on Linux and macOS. Every asset lookup
    goes through the roots below, which already know where each packaging
    step puts things.
    """
    for path in iter_qt_window_icon_candidates(project_root=project_root):
        if path.suffix.lower() == ".png":
            return path
    return None
