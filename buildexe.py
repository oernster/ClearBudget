"""Build standalone EXE with PyInstaller."""

import shutil
import subprocess
import sys
from pathlib import Path


def build_exe() -> int:
    """Create standalone EXE using PyInstaller."""
    print("Building ClearBudget EXE...")

    root = Path(__file__).parent
    dist_dir = root / "dist-pyinstaller"
    build_dir = root / "build"
    spec_file = root / "ClearBudget.spec"

    pyinstaller_exe = shutil.which("pyinstaller")
    if not pyinstaller_exe:
        print("Error: pyinstaller not found. Activate the venv and install requirements-dev.txt")
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
        "--noconfirm",
        "--distpath=dist-pyinstaller",
        "main.py",
    ]

    result = subprocess.run(cmd, cwd=root)
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
