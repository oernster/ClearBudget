"""GNU LGPL v3 license text for display in the installer UI."""

from __future__ import annotations

import sys
from pathlib import Path


def _read_lgpl3_text() -> str:
    """Load LGPL v3 text from repo-root `LICENSE`."""

    candidates: list[Path] = []

    # Each candidate is skipped rather than fatal: a location that cannot be
    # formed is simply not a place to look; the final FileNotFoundError names
    # every path that was tried.
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "LICENSE")
    except TypeError:
        # PyInstaller sets _MEIPASS to a str; anything else is not a path.
        pass

    try:
        candidates.append(Path(sys.executable).resolve().parent / "LICENSE")
    except OSError:
        # resolve() touches the filesystem and can fail on a broken path.
        pass

    try:
        candidates.append(Path(__file__).resolve().parents[2] / "LICENSE")
    except (OSError, IndexError):
        # IndexError if this module ever sits fewer than two levels deep.
        pass

    candidates.append(Path.cwd() / "LICENSE")

    for p in candidates:
        try:
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # Unreadable or vanished between the check and the read. Try the
            # next candidate; errors="replace" means decoding cannot fail.
            continue

    raise FileNotFoundError(
        "Unable to locate LICENSE. Tried: " + ", ".join(str(p) for p in candidates)
    )


LGPL_V3_TEXT = _read_lgpl3_text()
