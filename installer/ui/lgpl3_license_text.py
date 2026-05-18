"""GNU LGPL v3 license text for display in the installer UI.

Note:
    The project-level [`LICENSE`](LICENSE:1) file is intentionally *not* LGPLv3.
    This module exists solely to present the LGPLv3 text (used by components
    in the installer runtime, e.g. Qt for Python) inside the installer UI.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _read_lgpl3_text() -> str:
    """Load LGPL v3 text from repo-root `LGPL3-LICENSE`.

    This is a shared single source of truth for both runtime UI + installer UI.
    """

    candidates: list[Path] = []

    # PyInstaller onefile extracts bundled data files to sys._MEIPASS.
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "LGPL3-LICENSE")
    except Exception:
        pass

    # Next to the executable (frozen). In dev, this is the python.exe folder.
    try:
        candidates.append(Path(sys.executable).resolve().parent / "LGPL3-LICENSE")
    except Exception:
        pass

    # Repo layout fallback: installer/ui/lgpl3_license_text.py -> repo root is
    # parents[2].
    try:
        candidates.append(Path(__file__).resolve().parents[2] / "LGPL3-LICENSE")
    except Exception:
        pass

    candidates.append(Path.cwd() / "LGPL3-LICENSE")

    for p in candidates:
        try:
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

    raise FileNotFoundError(
        "Unable to locate LGPL3-LICENSE. Tried: "
        + ", ".join(str(p) for p in candidates)
    )


LGPL_V3_TEXT = _read_lgpl3_text()
