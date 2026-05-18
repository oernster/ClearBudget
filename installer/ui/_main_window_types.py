from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UiSelections:
    install_dir: Path
    shortcut_desktop: bool
    shortcut_start_menu: bool
