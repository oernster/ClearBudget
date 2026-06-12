#!/usr/bin/env python3
"""macOS DMG builder for ClearBudget.

Requires macOS with Xcode command-line tools and Homebrew.
Run from the repository root with the venv active:
    python builddmg.py

Optional env vars:
    DEVELOPER_ID_APPLICATION  — override the default signing identity
    APPLE_ID                  — Apple ID for notarization (skipped if not set)
    APPLE_APP_PASSWORD        — app-specific password for notarization
    APPLE_TEAM_ID             — Team ID for notarization (defaults to W7K465GKFJ)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from build_utils import require, run, section
from dmg_icon import png_to_icns, set_volume_icon


def _read_version() -> str:
    version_file = Path(__file__).parent / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "0.0.0-dev"


# ── Constants ──────────────────────────────────────────────────────────────────

APP_NAME = "ClearBudget"
APP_VERSION = _read_version()
BUNDLE_ID = "uk.codecrafter.ClearBudget"
FINAL_DMG = "clearbudget.dmg"
RW_DMG = "_clearbudget_rw.dmg"
VOLUME_NAME = f"Install {APP_NAME}"

# Source 1024x1024 icon and the runtime PNG bundled beside the binary.
SOURCE_PNG = "ClearBudget.png"

# Dark background matching ClearBudget's app theme (dark_theme.py base colour).
ICON_BG = (0x0A, 0x0A, 0x0D)

# Per-resolution PNGs bundled so the runtime QIcon lookup resolves, plus the
# Windows-style assets carried for parity with the EXE build.
BUNDLED_ICONS = [
    "ClearBudget_16.png",
    "ClearBudget_32.png",
    "ClearBudget_48.png",
    "ClearBudget_64.png",
    "ClearBudget_128.png",
    "ClearBudget_256.png",
    "ClearBudget_512.png",
    "ClearBudget.png",
    "ClearBudget.ico",
]

DEVELOPER_ID = os.environ.get(
    "DEVELOPER_ID_APPLICATION",
    "Developer ID Application: Oliver Ernster (W7K465GKFJ)",
)
APPLE_ID = os.environ.get("APPLE_ID", "")
APPLE_APP_PASSWORD = os.environ.get("APPLE_APP_PASSWORD", "")
APPLE_TEAM_ID = os.environ.get("APPLE_TEAM_ID", "W7K465GKFJ")

# Minimal hardened-runtime entitlements. ClearBudget is a local-first SQLite
# app with no network use and no JIT, so none of the relaxed memory/network
# entitlements are required. disable-library-validation lets the hardened
# runtime load the PyInstaller-bundled Qt frameworks signed with our identity.
ENTITLEMENTS = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
</dict>
</plist>
"""


# ── Steps ─────────────────────────────────────────────────────────────────────


def check_platform() -> None:
    section("Platform check")
    if sys.platform != "darwin":
        sys.exit("ERROR: This script must run on macOS.")
    result = subprocess.run(
        ["sw_vers", "-productVersion"], capture_output=True, text=True
    )
    print(f"  macOS {result.stdout.strip()}")
    require("pyinstaller", "pyinstaller")
    require("create-dmg", "create-dmg")
    require("codesign")
    print("  All tools present.")


def clean() -> None:
    section("Clean previous build")
    for path in [
        "build",
        "dist",
        FINAL_DMG,
        f"{APP_NAME}.spec",
        "_dmg_staging",
        RW_DMG,
    ]:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            print(f"  Removed: {path}")


def build_app_bundle(entitlements_path: Path, icns_path: Path | None = None) -> Path:
    section("PyInstaller: build .app bundle")

    root = Path(__file__).parent
    icon_args = ["--icon", str(icns_path)] if icns_path else []

    add_data = [f"{root / 'VERSION'}:.", f"{root / 'LICENSE'}:."]
    for name in BUNDLED_ICONS:
        asset = root / name
        if asset.exists():
            add_data.append(f"{asset}:.")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--osx-bundle-identifier",
        BUNDLE_ID,
        "--codesign-identity",
        DEVELOPER_ID,
        "--osx-entitlements-file",
        str(entitlements_path),
        *icon_args,
        # Pull in every clear_budget submodule, including any reached only via
        # function-level deferred imports in the composition root.
        "--collect-submodules=clear_budget",
    ]

    for spec in add_data:
        cmd.extend(["--add-data", spec])

    cmd.append(str(root / "main.py"))

    run(cmd)

    app_path = Path("dist") / f"{APP_NAME}.app"
    if not app_path.exists():
        sys.exit(f"ERROR: Expected app bundle not found: {app_path}")
    print(f"  Built: {app_path}")
    return app_path


def strip_build_artifacts(app_path: Path) -> None:
    section("Strip build artifacts")
    # PySide6 ships .cpp.o object files inside its QML plugin directories.
    # They are Mach-O relocatable binaries that codesign --deep silently skips
    # but Gatekeeper flags as unsigned, causing the entire bundle to be rejected.
    removed = 0
    for f in app_path.rglob("*.o"):
        if f.is_file():
            f.unlink()
            removed += 1
    for d in sorted(app_path.rglob("objects-*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    print(f"  Removed {removed} intermediate object file(s)")


def sign_bundle(app_path: Path, entitlements_path: Path) -> None:
    section("Code signing")

    run(
        [
            "codesign",
            "--force",
            "--deep",
            "--options",
            "runtime",
            "--entitlements",
            str(entitlements_path),
            "--sign",
            DEVELOPER_ID,
            str(app_path),
        ]
    )

    run(["codesign", "--verify", "--deep", "--strict", str(app_path)])
    print("  Signature verified.")


def create_dmg(app_path: Path) -> None:
    section("Create DMG")

    staging = Path("_dmg_staging")
    staging.mkdir(exist_ok=True)
    dest = staging / app_path.name
    if dest.exists():
        shutil.rmtree(dest)
    # ditto preserves the symlinks macOS frameworks rely on (e.g.
    # Python.framework/Python -> Versions/Current/Python). Dereferencing them
    # into regular files invalidates every embedded code signature and causes
    # dlopen failures at runtime.
    run(["ditto", str(app_path), str(dest)])

    if os.path.exists(FINAL_DMG):
        os.remove(FINAL_DMG)

    cmd = [
        "create-dmg",
        "--volname",
        VOLUME_NAME,
        "--window-pos",
        "200",
        "120",
        "--window-size",
        "640",
        "400",
        "--icon-size",
        "100",
        "--text-size",
        "14",
        "--app-drop-link",
        "520",
        "180",
        "--icon",
        f"{APP_NAME}.app",
        "120",
        "180",
        FINAL_DMG,
        str(staging / f"{APP_NAME}.app"),
    ]

    result = run(cmd, check=False)
    if result.returncode not in (0, 2):
        sys.exit(f"ERROR: create-dmg failed (exit {result.returncode})")

    shutil.rmtree(staging)
    print(f"  DMG created: {FINAL_DMG}")


def sign_dmg() -> None:
    section("Sign DMG")
    run(["codesign", "--force", "--sign", DEVELOPER_ID, FINAL_DMG])
    print("  DMG signed.")


def notarize_dmg() -> None:
    if not APPLE_ID or not APPLE_APP_PASSWORD:
        print(
            "\n  Notarization skipped (set APPLE_ID and APPLE_APP_PASSWORD to enable)."
        )
        return

    section("Notarize DMG")
    run(
        [
            "xcrun",
            "notarytool",
            "submit",
            FINAL_DMG,
            "--apple-id",
            APPLE_ID,
            "--password",
            APPLE_APP_PASSWORD,
            "--team-id",
            APPLE_TEAM_ID,
            "--wait",
        ]
    )
    run(["xcrun", "stapler", "staple", FINAL_DMG])
    print("  Notarization complete and stapled.")


def verify_dmg() -> None:
    section("Verify DMG")
    run(["codesign", "--verify", FINAL_DMG])
    size_mb = os.path.getsize(FINAL_DMG) / (1024 * 1024)
    print(f"  {FINAL_DMG}  ({size_mb:.1f} MB)  — ready for distribution")


def apply_file_icon(png_path: Path) -> None:
    section("Apply file icon")
    require("fileicon")
    run(["fileicon", "set", FINAL_DMG, str(png_path)])
    print(f"  Icon applied to {FINAL_DMG}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    print(f"\nCLEARBUDGET DMG BUILDER  v{APP_VERSION}")
    print(f"Signing identity: {DEVELOPER_ID}")

    check_platform()
    clean()

    with tempfile.NamedTemporaryFile(
        suffix=".entitlements", mode="w", delete=False
    ) as f:
        f.write(ENTITLEMENTS)
        entitlements_path = Path(f.name)

    with tempfile.TemporaryDirectory() as icon_tmp:
        png_path = Path(__file__).parent / SOURCE_PNG
        icns_path = (
            png_to_icns(png_path, Path(icon_tmp), ICON_BG)
            if png_path.exists()
            else None
        )
        if not icns_path:
            print(f"  WARNING: {png_path} not found — building without custom icon.")

        try:
            app_path = build_app_bundle(entitlements_path, icns_path)
            strip_build_artifacts(app_path)
            sign_bundle(app_path, entitlements_path)
            create_dmg(app_path)
            if icns_path:
                set_volume_icon(icns_path, FINAL_DMG, RW_DMG)
            sign_dmg()
            notarize_dmg()
            verify_dmg()
            if icns_path:
                apply_file_icon(png_path)
        finally:
            entitlements_path.unlink(missing_ok=True)

    print(f"\nDone.  Distribute: {FINAL_DMG}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
