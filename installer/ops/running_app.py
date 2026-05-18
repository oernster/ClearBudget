"""Detect whether ClearBudget is currently running."""

from __future__ import annotations

from pathlib import Path

import psutil


def is_app_running(exe_path: Path) -> bool:
    exe_path = exe_path.resolve()
    for proc in psutil.process_iter(attrs=["exe"]):
        try:
            pexe = proc.info.get("exe")
            if not pexe:
                continue
            if Path(pexe).resolve() == exe_path:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except Exception:
            # Best-effort; treat as not running if we cannot inspect.
            continue
    return False
