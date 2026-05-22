"""GNU LGPL v3 license text for display in the installer UI."""

from __future__ import annotations

import sys
from pathlib import Path


def _read_lgpl3_text() -> str:
    """Load LGPL v3 text from repo-root `LICENSE`."""

    candidates: list[Path] = []

    try:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "LICENSE")
    except Exception:
        pass

    try:
        candidates.append(Path(sys.executable).resolve().parent / "LICENSE")
    except Exception:
        pass

    try:
        candidates.append(Path(__file__).resolve().parents[2] / "LICENSE")
    except Exception:
        pass

    candidates.append(Path.cwd() / "LICENSE")

    for p in candidates:
        try:
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

    raise FileNotFoundError(
        "Unable to locate LICENSE. Tried: " + ", ".join(str(p) for p in candidates)
    )


LGPL_V3_TEXT = _read_lgpl3_text()
