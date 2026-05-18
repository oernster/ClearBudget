"""Build ClearBudgetSetup.exe (single-file per-user installer).

Workflow:

1) Build app bundle:     python buildexe.py
2) Build payload+setup:  python buildinstaller.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def _require_windows() -> None:
    if os.name != "nt":
        raise SystemExit("buildinstaller.py is Windows-only")


def _run(cmd: list[str]) -> None:
    print("\n> " + " ".join(cmd))
    subprocess.check_call(cmd)  # noqa: S603


def _retry_unlink(path: Path, *, attempts: int = 20, delay_s: float = 0.15) -> None:
    """Try to delete a file that may be briefly locked by AV/Explorer."""

    if not path.exists():
        return

    last_exc: Exception | None = None
    for _ in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(delay_s)
    if last_exc:
        raise last_exc


def _replace_file(src: Path, dst: Path) -> None:
    """Replace dst with src.

    On Windows, the destination may be locked if the exe is running.
    """

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        _retry_unlink(dst)
    shutil.move(str(src), str(dst))


def main() -> int:
    _require_windows()

    # 1) Build payload zip + manifest.
    _run([sys.executable, "-m", "installer.build_payload"])

    # 2) Build installer exe.
    final_dist_root = PROJECT_ROOT / "dist-installer"
    work_root = PROJECT_ROOT / "build" / "installer"

    # Build into a temporary dist folder and then move into place. This avoids
    # PyInstaller failing mid-build if an old ClearBudgetSetup.exe is still locked.
    temp_dist_root = PROJECT_ROOT / "dist-installer.build"

    for p in [temp_dist_root, work_root]:
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    entrypoint = PROJECT_ROOT / "installer" / "app.py"
    icon = PROJECT_ROOT / "ClearBudget.ico"

    payload_zip = PROJECT_ROOT / "installer" / "payload" / "payload.zip"
    manifest_json = PROJECT_ROOT / "installer" / "payload" / "manifest.json"

    if not payload_zip.exists() or not manifest_json.exists():
        raise SystemExit("Payload build did not produce payload.zip/manifest.json")

    # Include the icon file so the runtime can set the window/taskbar icon.
    # NOTE: This is separate from --icon, which only sets the embedded exe icon.
    add_data = [
        f"{payload_zip};installer/payload",
        f"{manifest_json};installer/payload",
        # Version file (read by clear_budget.version module).
        f"{PROJECT_ROOT / 'VERSION'};.",
        # Licences (shown in installer UI and shipped for runtime UI dialogs).
        f"{PROJECT_ROOT / 'LICENSE'};.",
        f"{PROJECT_ROOT / 'LGPL3-LICENSE'};.",
        # Ship icon assets so the installer can set its own window icon and so
        # it can deploy them next to ClearBudget.exe (for taskbar + shortcut icon
        # consistency).
        f"{icon};.",
        f"{PROJECT_ROOT / 'clearbudget_16.png'};.",
        f"{PROJECT_ROOT / 'clearbudget_32.png'};.",
        f"{PROJECT_ROOT / 'clearbudget_48.png'};.",
        f"{PROJECT_ROOT / 'clearbudget_64.png'};.",
        f"{PROJECT_ROOT / 'clearbudget_128.png'};.",
        f"{PROJECT_ROOT / 'clearbudget_256.png'};.",
        f"{PROJECT_ROOT / 'clearbudget_512.png'};.",
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "ClearBudgetSetup",
        "--distpath",
        str(temp_dist_root),
        "--workpath",
        str(work_root),
    ]
    for spec in add_data:
        cmd.extend(["--add-data", spec])

    # Ensure new UI worker module is included.
    cmd.extend(["--hidden-import", "installer.ui.worker"])

    cmd.append(str(entrypoint))
    _run(cmd)

    built_exe = temp_dist_root / "ClearBudgetSetup.exe"
    final_exe = final_dist_root / "ClearBudgetSetup.exe"

    if built_exe.exists():
        try:
            _replace_file(built_exe, final_exe)
        except PermissionError as exc:
            raise SystemExit(
                "Unable to overwrite the installer EXE because it is in use.\n"
                "Close any running installer instances.\n"
                "Then try again."
            ) from exc

        # Clean up temp dist folder.
        shutil.rmtree(temp_dist_root, ignore_errors=True)

        print(f"\nBuilt: {final_exe}")
        return 0

    print("\nBuild finished; expected installer exe not found.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
