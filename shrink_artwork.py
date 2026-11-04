"""Resample the view and tray artwork to the size a build should ship it at.

The masters at the repository root are 1254 px squares and wider, 1.2 to 2 MB
each: nineteen of them put 27 MB into every package, which was more than the
whole of Qt Widgets. The application draws them at `VIEW_ICON_PX` (26) and
`_INLINE_ICON_PX` (30) logical pixels; `ui_scale` caps its factor at 2.0, so
nothing is ever drawn above 60 px. A 256 px copy keeps more than four times
that in hand for a high device pixel ratio and weighs about 50 KB.

The masters stay where they are, untouched, as the source for the site and for
any future size. This script writes the shipped copies into a build directory
and every delivery script stages those: `buildexe.py`, `buildinstaller.py`,
`builddmg.py` and `build_flatpak.sh`.

It resamples through Qt rather than Pillow because every build machine has
PySide6 and none is required to have Pillow. `QImage` loads, scales and saves
a PNG with no QGuiApplication running (measured on 2026-11-04).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from clear_budget.shared.resources import _VIEW_ICON_NAMES

PROJECT_ROOT = Path(__file__).resolve().parent

# The longest edge of a shipped copy. See the module docstring for where the
# headroom comes from; it is also the edge the application icon already ships
# at, which the Graph button wears from the same slots as these pictures.
SHIPPED_EDGE_PX = 256

ARTWORK = tuple(sorted(_VIEW_ICON_NAMES))


def shrink(out_dir: Path, *, root: Path = PROJECT_ROOT) -> list[Path]:
    """Write a shipped copy of every picture into `out_dir`; return them.

    A master already within the edge is copied byte for byte, so the sized
    application icon in the same list passes through unchanged.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in ARTWORK:
        source = root / name
        target = out_dir / name
        image = QImage(str(source))
        if image.isNull():
            raise SystemExit(f"cannot read {source}")
        longest = max(image.width(), image.height())
        if longest <= SHIPPED_EDGE_PX:
            shutil.copyfile(source, target)
        else:
            scaled = image.scaled(
                SHIPPED_EDGE_PX,
                SHIPPED_EDGE_PX,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if not scaled.save(str(target), "PNG"):
                raise SystemExit(f"cannot write {target}")
        written.append(target)
    return written


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: shrink_artwork.py <output directory>")
        return 2
    out_dir = Path(argv[1])
    written = shrink(out_dir)
    total = sum(p.stat().st_size for p in written)
    print(f"  {len(written)} pictures written to {out_dir}, {total / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
