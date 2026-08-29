"""Emit every derived image asset from its master PNG at the repo root.

Replaces two scripts that used to sit here. `create_icon.py` rebuilt the `.ico`
from whichever PNGs happened to be on disk; `create_icons.py` drew a wallet
symbol procedurally with PIL. Neither was the source of the tracked assets:
the procedural drawing does not match them at any size and paints an opaque
background, where the real icon has fully transparent corners. Running it would
have replaced a designed icon with a generated one.

`ClearBudget.png` is the master, 1024x1024 RGBA. Every tracked size is
bit-identical to a Lanczos resize of it, which is what makes this script
checkable rather than merely plausible: run it on a clean tree and `git status`
stays empty.

`donate.png` is a second master, for the footer's donate button. It is
handled separately because it is not an icon. It is a wide picture drawn at a
button's height, so squaring it would spend half the height on empty canvas.
The APPLICATION needs nothing derived from it: `image_icon_pixmap` crops and
scales the full-size master at runtime, the same as every other tray picture.
The SITE cannot do that, so the one derived copy here is `docs/donate.png`,
cropped to its artwork and scaled by height alone.
"""

from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).parent

MASTER_PNG = "ClearBudget.png"
ICO_NAME = "ClearBudget.ico"

# Emitted PNG edge lengths, largest first so the report reads top down.
PNG_SIZES = (512, 256, 128, 64, 48, 32, 16)

# Sizes carried inside the multi-resolution Windows icon, the portfolio's
# standard set. 24 is here although no 24 PNG is tracked, because the icon is
# built from the master rather than from the emitted files. Neither script this
# replaces produced 24, which is how it was established that neither of them
# built the tracked `.ico` either.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

# The donate button's own master and the single copy derived from it. The
# height is four times what the landing page draws it at, so the button stays
# crisp under display scaling without the master's megabytes reaching the site.
DONATE_MASTER = "donate.png"
DONATE_COPY = Path("docs") / "donate.png"
DONATE_HEIGHT_PX = 116


def _png_name(size: int) -> str:
    return f"ClearBudget_{size}.png"


def _load_master(root: Path) -> Image.Image:
    master = Image.open(root / MASTER_PNG).convert("RGBA")
    if master.width != master.height:
        raise ValueError(f"{MASTER_PNG} must be square, got {master.size}")
    return master


def _write_pngs(master: Image.Image, root: Path) -> None:
    for size in PNG_SIZES:
        resized = master.resize((size, size), Image.LANCZOS)
        path = root / _png_name(size)
        resized.save(path, "PNG")
        print(f"  [OK] {path.name}")


def _write_ico(master: Image.Image, root: Path) -> None:
    path = root / ICO_NAME
    master.save(path, format="ICO", sizes=[(size, size) for size in ICO_SIZES])
    print(f"  [OK] {path.name} ({path.stat().st_size} bytes)")


def _write_donate(root: Path) -> None:
    """Derive the site's copy of the donate artwork from its own master.

    Cropped to the tight box of its non-transparent pixels first, so the copy
    is sized by the artwork rather than by however much empty canvas its author
    left around it, then scaled by HEIGHT alone so the aspect ratio survives.
    """
    master = Image.open(root / DONATE_MASTER).convert("RGBA")
    box = master.getchannel("A").getbbox()
    if box is None:
        raise ValueError(f"{DONATE_MASTER} has no opaque artwork to crop to")
    art = master.crop(box)
    width = max(1, round(art.width * DONATE_HEIGHT_PX / art.height))
    resized = art.resize((width, DONATE_HEIGHT_PX), Image.LANCZOS)
    path = root / DONATE_COPY
    path.parent.mkdir(parents=True, exist_ok=True)
    resized.save(path, "PNG")
    print(f"  [OK] {DONATE_COPY.as_posix()} ({resized.width}x{resized.height})")


def main() -> int:
    root = PROJECT_ROOT
    master = _load_master(root)
    print(f"Master: {MASTER_PNG} ({master.width}x{master.height})")
    _write_pngs(master, root)
    _write_ico(master, root)
    print(f"Master: {DONATE_MASTER}")
    _write_donate(root)
    print("Image generation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
