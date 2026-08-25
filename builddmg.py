#!/usr/bin/env python3
"""macOS DMG builder for ClearBudget.

Requires macOS with Xcode command-line tools and Homebrew.
Run from the repository root with the venv active:
    python builddmg.py

Notarization is mandatory. A Developer ID signature alone is not enough: since
macOS 10.15 Gatekeeper rejects signed-but-unnotarized apps with "Apple could not
verify ... is free of malware". Credentials come from this app's keychain
profile (NOTARY_PROFILE), stored once with `xcrun notarytool store-credentials`,
so nothing needs to be exported to run a release build.

Env vars:
    APPLE_KEYCHAIN_PROFILE    : override the per-app keychain profile
    APPLE_ID                  : Apple ID, for CI that has no keychain
    APPLE_APP_PASSWORD        : app-specific password, paired with APPLE_ID
    DEVELOPER_ID_APPLICATION  : override the default signing identity
    APPLE_TEAM_ID             : Team ID for notarization (defaults to W7K465GKFJ)
    ALLOW_UNNOTARIZED         : set to 1 to build without notarizing. The result
                                is for local testing only and must never be
                                published as a release artifact.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

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

# Dark background matching ClearBudget's dark theme (theme_tokens window_bg).
ICON_BG = (0x0A, 0x0A, 0x0D)

# Per-resolution PNGs bundled so the runtime QIcon lookup resolves, plus the
# Windows-style assets carried for parity with the EXE build. The three
# tab-strip images are in this list rather than a second one because they are
# staged the same way and read through the same resource lookup; splitting
# them would be two lists to keep in step with one packaging step.
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
    "monthlybudget.png",
    "solvency.png",
    "creditcards.png",
    "bank-icon.png",
    "bank-icon2.png",
    "creditcards2.png",
    "exporttohtml.png",
    "switchbudget.png",
    "opendb.png",
    "savedb.png",
    "information.png",
    "archive.png",
    "recommendations.png",
    "exportpackage.png",
    "lightmode.png",
    "darkmode.png",
]

DEVELOPER_ID = os.environ.get(
    "DEVELOPER_ID_APPLICATION",
    "Developer ID Application: Oliver Ernster (W7K465GKFJ)",
)
APPLE_ID = os.environ.get("APPLE_ID", "")
APPLE_APP_PASSWORD = os.environ.get("APPLE_APP_PASSWORD", "")
APPLE_TEAM_ID = os.environ.get("APPLE_TEAM_ID", "W7K465GKFJ")

# The notarization credential for this app, created once with
#   xcrun notarytool store-credentials ClearBudget \
#     --apple-id <id> --team-id <team> --password <app-specific>
# One profile per app means a leaked credential can be revoked for a single
# app. Stated explicitly rather than derived from a display name: the profile
# is a fact registered with Apple; deriving it would silently change which
# credential the build looks for if that name were ever edited.
# APPLE_KEYCHAIN_PROFILE overrides it.
NOTARY_PROFILE = os.environ.get("APPLE_KEYCHAIN_PROFILE", "") or "ClearBudget"

# The notary service accepts only an app-specific password from appleid.apple.com
# and rejects the Apple account password with HTTP 401. The shape is distinctive,
# so it is checked before the build rather than discovered after it.
APP_SPECIFIC_PASSWORD_RE = re.compile(r"^[a-z]{4}-[a-z]{4}-[a-z]{4}-[a-z]{4}$")

# Escape hatch for local test builds. Distribution builds must never set this:
# an unnotarized DMG is rejected by Gatekeeper on every machine but the one that
# signed it; the failure is invisible at build time.
ALLOW_UNNOTARIZED = os.environ.get("ALLOW_UNNOTARIZED", "") == "1"

# Notarization is the default and the keychain profile always resolves, so the
# only way to skip it is to ask for that explicitly.
NOTARIZING = not ALLOW_UNNOTARIZED

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
        ["sw_vers", "-productVersion"], capture_output=True, text=True, check=False
    )
    print(f"  macOS {result.stdout.strip()}")
    require("pyinstaller", "pyinstaller")
    require("create-dmg", "create-dmg")
    require("codesign")
    print("  All tools present.")


def check_notarization_credentials() -> None:
    """Fail before the build starts if the release cannot be notarized.

    Checked up front rather than at the notarization step so a missing password
    costs seconds instead of a full PyInstaller run.
    """
    section("Notarization credentials")
    if ALLOW_UNNOTARIZED:
        print("  WARNING: ALLOW_UNNOTARIZED=1 set.")
        print("  WARNING: this build is for local testing and must not be released.")
        return
    if APPLE_ID and APPLE_APP_PASSWORD:
        if not APP_SPECIFIC_PASSWORD_RE.match(APPLE_APP_PASSWORD):
            sys.exit(
                "ERROR: APPLE_APP_PASSWORD is not an app-specific password.\n"
                "  Expected four lowercase groups of four, like abcd-efgh-ijkl-mnop.\n"
                "  An Apple account password is rejected by the notary service with\n"
                "  'HTTP status code: 401. Invalid credentials'.\n"
                "  Generate one at https://appleid.apple.com (Sign-In and Security,\n"
                "  App-Specific Passwords); or leave both variables unset and store\n"
                f"  the credential in the keychain as profile {NOTARY_PROFILE}."
            )
        print(f"  Notarizing as {APPLE_ID} (team {APPLE_TEAM_ID}).")
        return
    print(f"  Notarizing with keychain profile {NOTARY_PROFILE}.")


def check_runtime_dependencies() -> None:
    """Fail if anything in requirements.txt is absent from the build interpreter.

    PyInstaller only warns when --collect-submodules names a package it cannot
    find, so a stale venv yields a bundle that builds, signs and notarizes
    cleanly and then dies at launch with ModuleNotFoundError. That is exactly how
    a release shipped without keyring after the Remember me feature landed.
    Checking the interpreter that is about to be frozen turns a silent runtime
    failure into a build failure.
    """
    section("Runtime dependencies")
    requirements = Path(__file__).parent / "requirements.txt"
    if not requirements.exists():
        sys.exit(f"ERROR: {requirements.name} not found beside builddmg.py.")

    missing: list[str] = []
    checked = 0
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        # Skip blanks and pip options such as -r or --index-url. Distribution
        # names are what requirements.txt lists, so no import-name mapping is
        # needed: PySide6 and pyobjc-framework-Cocoa both resolve here.
        if not line or line.startswith("-"):
            continue
        try:
            requirement = Requirement(line)
        except InvalidRequirement as error:
            sys.exit(f"ERROR: cannot parse '{line}' in {requirements.name}: {error}")
        # An environment marker such as sys_platform == "win32" means the package
        # is not wanted on this platform, so its absence is correct rather than a
        # fault. Evaluating the marker beats naming Windows packages here, which
        # would go stale the moment the requirements change.
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        checked += 1
        try:
            metadata.version(requirement.name)
        except metadata.PackageNotFoundError:
            missing.append(requirement.name)

    if missing:
        sys.exit(
            "ERROR: the build interpreter is missing "
            f"{len(missing)} of {checked} requirements:\n"
            + "".join(f"    {name}\n" for name in missing)
            + "  PyInstaller would omit them and the app would crash at launch\n"
            "  with ModuleNotFoundError. Install them first:\n"
            f"    pip install -r {requirements.name}"
        )
    print(f"  All {checked} requirements present.")


def notarytool_credentials() -> list[str]:
    """Authentication arguments for notarytool.

    An explicit APPLE_ID and APPLE_APP_PASSWORD pair wins, for CI that has no
    keychain. Otherwise the per-app profile is used, which keeps the secret out
    of the process arguments where any other process could read it via ps.
    """
    if APPLE_ID and APPLE_APP_PASSWORD:
        return [
            "--apple-id",
            APPLE_ID,
            "--password",
            APPLE_APP_PASSWORD,
            "--team-id",
            APPLE_TEAM_ID,
        ]
    return ["--keychain-profile", NOTARY_PROFILE]


def redact(cmd: list[str]) -> str:
    """Render a command with the value after --password masked.

    build_utils.run echoes every command it runs; CalledProcessError repeats
    the whole argument list in its traceback. Both would otherwise copy the
    app-specific password into build logs and CI output.
    """
    parts: list[str] = []
    mask_next = False
    for arg in (str(c) for c in cmd):
        parts.append("********" if mask_next else arg)
        mask_next = arg == "--password"
    return " ".join(parts)


def notarytool_submit(target: Path) -> None:
    """Submit target to Apple and wait for the verdict.

    A failed submission stops the build rather than producing an artifact that
    looks distributable. subprocess is called directly instead of through run()
    so that neither the echoed command nor the failure path exposes the
    password. Stapling is a separate step because the submitted file and the
    file that carries the ticket differ for a .app (a zip is submitted, the
    bundle is stapled).
    """
    cmd = [
        "xcrun",
        "notarytool",
        "submit",
        str(target),
        *notarytool_credentials(),
        "--wait",
    ]
    print(f"  $ {redact(cmd)}")
    if subprocess.run(cmd, check=False).returncode == 0:
        return
    sys.exit(
        "ERROR: notarization failed (notarytool output above).\n"
        "  'No Keychain password item found' means this app has no stored\n"
        "  credential yet. Generate an app-specific password at\n"
        "  https://appleid.apple.com (Sign-In and Security), then:\n"
        f"    xcrun notarytool store-credentials {NOTARY_PROFILE} \\\n"
        "      --apple-id you@example.com --team-id "
        f"{APPLE_TEAM_ID} --password <app-specific>\n"
        "  'HTTP status code: 401' means the credential is wrong: use an\n"
        "  app-specific password, not your Apple account password.\n"
        "  For an 'Invalid' verdict, the per-binary reasons are in:\n"
        "    xcrun notarytool log <submission-id> "
        f"--keychain-profile {NOTARY_PROFILE}"
    )


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
    # A missing asset FAILS the build rather than being skipped. Skipping it
    # produced a bundle that launched perfectly with a control wearing no
    # picture, discoverable only by running the packaged app and looking; the
    # build itself reported success. An asset named here and not on disk is a
    # mistake in one place or the other; either way it is not shippable.
    missing = [name for name in BUNDLED_ICONS if not (root / name).exists()]
    if missing:
        raise SystemExit(
            "cannot build: these bundled assets are named but not on disk:\n  "
            + "\n  ".join(missing)
        )
    add_data.extend(f"{root / name}:." for name in BUNDLED_ICONS)

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
        # keyring discovers its OS backends via entry points, which PyInstaller
        # cannot see statically; collect them all so Remember me works frozen.
        "--collect-submodules=keyring",
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


def notarize_bundle(app_path: Path) -> None:
    """Notarize and staple the .app before it is placed in the DMG.

    Stapling only the DMG leaves the copied-out .app with no local ticket, so
    Gatekeeper falls back to an online check and the app fails to launch for a
    user who is offline or behind a restrictive network. notarytool only accepts
    archives, so the bundle is zipped with ditto first (ditto preserves the
    symlinks and metadata the embedded signature depends on); the ticket is then
    stapled to the bundle itself, since a zip cannot carry one.
    """
    if not NOTARIZING:
        return
    section("Notarize .app bundle")
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / f"{APP_NAME}.zip"
        run(["ditto", "-c", "-k", "--keepParent", str(app_path), str(archive)])
        notarytool_submit(archive)
    run(["xcrun", "stapler", "staple", str(app_path)])
    print("  Bundle notarized and stapled.")


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
    if not NOTARIZING:
        return
    section("Notarize DMG")
    notarytool_submit(Path(FINAL_DMG))
    run(["xcrun", "stapler", "staple", FINAL_DMG])
    print("  Notarization complete and stapled.")


def verify_dmg() -> None:
    section("Verify DMG")
    run(["codesign", "--verify", FINAL_DMG])
    if not NOTARIZING:
        size_mb = os.path.getsize(FINAL_DMG) / (1024 * 1024)
        print(f"  {FINAL_DMG}  ({size_mb:.1f} MB): UNNOTARIZED, local testing only")
        return
    # stapler validate proves a ticket is attached; spctl replays the check
    # Gatekeeper performs on the end user's machine. Together they catch the
    # silent case where signing succeeded but notarization never happened.
    run(["xcrun", "stapler", "validate", FINAL_DMG])
    run(["spctl", "--assess", "--type", "install", "-vv", FINAL_DMG])
    size_mb = os.path.getsize(FINAL_DMG) / (1024 * 1024)
    print(f"  {FINAL_DMG}  ({size_mb:.1f} MB): notarized, ready for distribution")


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
    check_runtime_dependencies()
    check_notarization_credentials()
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
            print(f"  WARNING: {png_path} not found; building without custom icon.")

        try:
            app_path = build_app_bundle(entitlements_path, icns_path)
            strip_build_artifacts(app_path)
            sign_bundle(app_path, entitlements_path)
            notarize_bundle(app_path)
            create_dmg(app_path)
            # Both icon steps rewrite the DMG, so they run before it is signed
            # and notarized. Doing either afterwards would modify a file that
            # Gatekeeper has already been told the hash of.
            if icns_path:
                set_volume_icon(icns_path, FINAL_DMG, RW_DMG)
                apply_file_icon(png_path)
            sign_dmg()
            notarize_dmg()
            verify_dmg()
        finally:
            entitlements_path.unlink(missing_ok=True)

    print(f"\nDone.  Distribute: {FINAL_DMG}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
