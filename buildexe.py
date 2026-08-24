"""Build standalone EXE with PyInstaller."""

import shutil
import subprocess
import sys
from pathlib import Path

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
            "Error: pyinstaller not found. Activate the venv and install requirements-dev.txt"
        )
        return 1

    if spec_file.exists():
        spec_file.unlink()

    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    if build_dir.exists():
        shutil.rmtree(build_dir)

    cmd = [
        pyinstaller_exe,
        "--name=ClearBudget",
        "--onedir",
        "--windowed",
        "--add-data=clear_budget:clear_budget",
        # ONE sized PNG, not the seven this used to carry. Every consumer of
        # the app icon takes the FIRST png from one ordered list
        # (`resources._QT_ICON_NAMES`) with the 256 at the head of it, so with
        # the 256 present the 128, 64, 48, 32 and 16 could never be selected
        # by any code path: they were bytes that shipped and were never read.
        # `main._find_runtime_icon` and `find_splash_image_path` name the 256
        # and nothing else. Staged lower-cased because that is the name those
        # two look for; the repository ships it capitalised and PyInstaller
        # stages a file under whatever name it is given here.
        "--add-data=clearbudget_256.png:.",
        # No ICO here on purpose. Nothing in the application ever asks for one:
        # `find_app_icon_path` and `find_qt_window_icon_path` are called only by
        # the SETUP program, which carries its own copy and deploys it beside
        # ClearBudget.exe (`installer/ops/registration`), which is what the
        # shortcut and the Apps list point at. An ICO staged here would be read
        # by nobody.
        # The tab-strip artwork, read at runtime by ui/utils/tab_icons.
        "--add-data=monthlybudget.png:.",
        "--add-data=solvency.png:.",
        "--add-data=creditcards.png:.",
        # The Graph tab wears the app icon and its bank/cards switch wears
        # the bank picture; both are read through the same lookup.
        "--add-data=ClearBudget_256.png:.",
        "--add-data=bank-icon.png:.",
        "--add-data=bank-icon2.png:.",
        "--add-data=creditcards2.png:.",
        "--add-data=VERSION:.",
        # keyring discovers its OS backends via entry points, which PyInstaller
        # cannot see statically; collect them all so Remember me works frozen.
        "--collect-submodules=keyring",
        "--noconfirm",
        "--distpath=dist-pyinstaller",
        "main.py",
    ]

    result = subprocess.run(cmd, cwd=root, check=False)
    if result.returncode != 0:
        print("PyInstaller build failed")
        return 1

    exe_path = dist_dir / "ClearBudget" / "ClearBudget.exe"
    if exe_path.exists():
        print(f"[OK] EXE created: {exe_path}")
        print(f"Size: {exe_path.stat().st_size / (1024*1024):.1f} MB")
        return 0

    print("EXE not found after build")
    return 1


if __name__ == "__main__":
    sys.exit(build_exe())
