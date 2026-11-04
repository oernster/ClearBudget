"""Build standalone EXE with PyInstaller."""

import shutil
import subprocess
import sys
from pathlib import Path

import build_prune
import shrink_artwork
import stamp_version


def build_exe() -> int:
    """Create standalone EXE using PyInstaller."""
    print("Building ClearBudget EXE...")

    # Propagate the canonical VERSION into static docs before packaging, so a
    # release never ships docs whose version disagrees with VERSION.
    stamp_version.main()

    root = Path(__file__).parent
    dist_dir = root / "dist-pyinstaller"
    build_dir = root / "build"
    spec_file = root / "ClearBudget.spec"

    pyinstaller_exe = shutil.which("pyinstaller")
    if not pyinstaller_exe:
        print(
            "Error: pyinstaller not found. Activate the venv and install "
            "requirements-dev.txt"
        )
        return 1

    if spec_file.exists():
        spec_file.unlink()

    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    if build_dir.exists():
        shutil.rmtree(build_dir)

    # The pictures ship at the size they are drawn at, not at the size they
    # were painted at; the masters at the root stay as they are.
    artwork = build_dir / "artwork"
    shrink_artwork.shrink(artwork)

    cmd = [
        pyinstaller_exe,
        "--name=ClearBudget",
        "--onedir",
        "--windowed",
        # The embedded PE icon, what Explorer and the taskbar show for the
        # bare exe. Without it PyInstaller embeds its own default, a diskette.
        # Unrelated to the staged PNGs below, which are runtime lookups.
        f"--icon={root / 'ClearBudget.ico'}",
        "--add-data=clear_budget:clear_budget",
        # ONE sized PNG, not the seven this used to carry. Every consumer of
        # the app icon takes the FIRST png from one ordered list
        # (`resources._QT_ICON_NAMES`) with the 256 at the head of it, so with
        # the 256 present the 128, 64, 48, 32 and 16 could never be selected
        # by any code path: they were bytes that shipped and were never read.
        # `find_runtime_window_icon` and `find_splash_image_path` name the 256
        # and nothing else. Staged under the repository's own spelling, the one
        # name every build uses: PyInstaller stages a file under whatever name
        # it is given, so a lower-cased name here would only work on a
        # filesystem that ignores case. The Graph button wears this same file.
        f"--add-data={artwork / 'ClearBudget_256.png'}:.",
        # No ICO here on purpose. Nothing in the application ever asks for one:
        # `find_app_icon_path` and `find_qt_window_icon_path` are called only by
        # the SETUP program, which carries its own copy and deploys it beside
        # ClearBudget.exe (`installer/ops/registration`), which is what the
        # shortcut and the Apps list point at. An ICO staged here would be read
        # by nobody.
        # The tab-strip artwork, read at runtime by ui/utils/tab_icons.
        f"--add-data={artwork / 'monthlybudget.png'}:.",
        f"--add-data={artwork / 'solvency.png'}:.",
        f"--add-data={artwork / 'creditcards.png'}:.",
        # The Graph page's bank/cards switch wears the bank picture.
        f"--add-data={artwork / 'bank-icon.png'}:.",
        f"--add-data={artwork / 'bank-icon2.png'}:.",
        f"--add-data={artwork / 'creditcards2.png'}:.",
        f"--add-data={artwork / 'exporttohtml.png'}:.",
        f"--add-data={artwork / 'switchbudget.png'}:.",
        f"--add-data={artwork / 'opendb.png'}:.",
        f"--add-data={artwork / 'savedb.png'}:.",
        f"--add-data={artwork / 'information.png'}:.",
        f"--add-data={artwork / 'archive.png'}:.",
        f"--add-data={artwork / 'recommendations.png'}:.",
        f"--add-data={artwork / 'reserves.png'}:.",
        f"--add-data={artwork / 'exportpackage.png'}:.",
        f"--add-data={artwork / 'lightmode.png'}:.",
        f"--add-data={artwork / 'darkmode.png'}:.",
        f"--add-data={artwork / 'donate.png'}:.",
        "--add-data=VERSION:.",
        # keyring discovers its OS backends via entry points, which PyInstaller
        # cannot see statically; collect that package so Remember me works
        # frozen. The backends package rather than all of keyring, because
        # keyring.testing imports pytest and brought it, pluggy and pygments
        # into the bundle.
        "--collect-submodules=keyring.backends",
        # What the Qt hooks would otherwise bring: QtNetwork, whose hook
        # collects the TLS plugins and whatever OpenSSL it finds on the build
        # machine. The Qt libraries and plugins the hooks add as binaries are
        # pruned from the folder below.
        *(f"--exclude-module={name}" for name in build_prune.EXCLUDED_MODULES),
        "--noconfirm",
        "--distpath=dist-pyinstaller",
        "main.py",
    ]

    result = subprocess.run(cmd, cwd=root, check=False)
    if result.returncode != 0:
        print("PyInstaller build failed")
        return 1

    bundle_dir = dist_dir / "ClearBudget"
    exe_path = bundle_dir / "ClearBudget.exe"
    if exe_path.exists():
        print("Pruning what the application never loads...")
        build_prune.prune_and_verify(bundle_dir)
        print(f"[OK] EXE created: {exe_path}")
        print(f"Size: {exe_path.stat().st_size / (1024*1024):.1f} MB")
        return 0

    print("EXE not found after build")
    return 1


if __name__ == "__main__":
    sys.exit(build_exe())
