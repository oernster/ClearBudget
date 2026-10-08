"""Every sized app icon is named as the repository spells it.

The icons are tracked as `ClearBudget_<size>.png`. For a long time the build
scripts, the setup program and the runtime lookup asked for
`clearbudget_<size>.png` instead. Windows and a default macOS volume ignore
case, so nothing failed where the builds run; a source checkout on Linux has
no file by that name, so the window opened with no icon there. One spelling
everywhere means a name that works on one filesystem works on all of them.

The truth is the directory listing, which reports a name's real case even on
a filesystem that ignores case when opening it.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_ICON_NAME = re.compile(r"\b[Cc][Ll][Ee][Aa][Rr][Bb][Uu][Dd][Gg][Ee][Tt]_\d+\.png\b")
_SCANNED_DIRS = ("clear_budget", "installer", "tests")
_ROOT_SUFFIXES = (".py", ".sh")


def _tracked_icons() -> set[str]:
    return {name for name in os.listdir(_ROOT) if _ICON_NAME.fullmatch(name)}


def _scanned_files() -> list[Path]:
    files = [
        path
        for path in _ROOT.iterdir()
        if path.is_file() and path.suffix in _ROOT_SUFFIXES
    ]
    for folder in _SCANNED_DIRS:
        files.extend((_ROOT / folder).rglob("*.py"))
    return files


def _misspelt() -> list[str]:
    tracked = _tracked_icons()
    found = []
    for path in _scanned_files():
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name in _ICON_NAME.findall(line):
                if name not in tracked:
                    rel = path.relative_to(_ROOT)
                    found.append(f"{rel}:{line_no}: {name}")
    return found


def test_the_icons_are_where_the_check_expects_them() -> None:
    """Worthless if the listing finds no icons to compare against."""
    assert _tracked_icons(), "no ClearBudget_<size>.png found at the repo root"


def test_every_icon_name_matches_the_tracked_file_exactly() -> None:
    offenders = _misspelt()
    assert (
        not offenders
    ), "icon names that differ from the tracked file, if only in case:\n" + "\n".join(
        offenders
    )
