#!/usr/bin/env bash
# build_flatpak.sh - Build ClearBudget as a Flatpak
#
# Uses org.freedesktop.Platform//25.08 (Python 3.13, glibc 2.42).
# ClearBudget is a pure PySide6 + bcrypt + SQLite desktop app: no native
# toolchains, no model downloads, no network at runtime.  The two Python
# wheels are pre-downloaded on the host, then installed inside the sandbox
# from those local wheels with --no-index, so the build itself is offline.
#
# Usage:
#   ./build_flatpak.sh             - build, install locally, AND produce clearbudget.flatpak
#   ./build_flatpak.sh --no-bundle - build + install only (skip the distributable bundle)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/venv/bin/activate"

APP_ID="com.oliverernster.clearbudget"
APP_VERSION=$(tr -d '[:space:]' < VERSION)
BUNDLE="clearbudget.flatpak"
BUILD_DIR=".flatpak-build"
REPO_DIR=".flatpak-repo"
MANIFEST="${APP_ID}.yml"

RUNTIME="org.freedesktop.Platform"
SDK="org.freedesktop.Sdk"
RUNTIME_VERSION="25.08"

# Python version shipped by the runtime above.  Used to build the site-packages
# path the launcher exports; keep it in sync with RUNTIME_VERSION.
PYTHON_MM="3.13"

# Wheels are tagged for the runtime's Python and glibc.  manylinux_2_34 is the
# tag PySide6's cp-abi3 wheels use; pip expands it to also accept every lower
# manylinux tag, so this single target covers PySide6, shiboken6 and bcrypt.
WHEEL_PYTHON="3.13"
WHEEL_PLATFORM="manylinux_2_34_x86_64"

# The distributable bundle is the whole point of this script, so it is built by
# default.  Pass --no-bundle to skip it and only build + install locally.
MAKE_BUNDLE=1
for arg in "$@"; do [[ "$arg" == "--no-bundle" ]] && MAKE_BUNDLE=0; done

# ── Colour helpers ────────────────────────────────────────────────────────────
bold=$(tput bold 2>/dev/null || true)
reset=$(tput sgr0 2>/dev/null || true)
section() { echo; echo "${bold}=== $* ===${reset}"; }

run_with_spinner() {
    local label="$1" watch=""
    shift
    if [[ "${1:-}" == "--watch" ]]; then watch="$2"; shift 2; fi
    [[ "${1:-}" == "--" ]] && shift
    "$@" &
    local pid=$! i=0 spin='⣾⣽⣻⢿⡿⣟⣯⣷'
    while kill -0 "$pid" 2>/dev/null; do
        local extra=""
        if [[ -n "$watch" && -f "$watch" ]]; then
            extra="  ($(du -sh "$watch" 2>/dev/null | cut -f1) written)"
        fi
        printf "\r  %s  %s%s" "${spin:$((i % ${#spin})):1}" "$label" "$extra"
        i=$((i + 1)); sleep 0.3
    done
    wait "$pid"; local rc=$?
    [[ $rc -eq 0 ]] && printf "\r  ✓  %-72s\n" "$label" \
                     || printf "\r  ✗  %-72s\n" "$label"
    return $rc
}

# ── Tool checks ───────────────────────────────────────────────────────────────
section "Checking dependencies"
install_if_missing() {
    local pkg="$1"
    if ! command -v "$pkg" &>/dev/null; then
        echo "  $pkg not found - installing..."
        if   command -v apt-get &>/dev/null; then sudo apt-get update -qq && sudo apt-get install -y "$pkg"
        elif command -v dnf    &>/dev/null; then sudo dnf install -y "$pkg"
        elif command -v pacman &>/dev/null; then sudo pacman -Sy --noconfirm "$pkg"
        else echo "ERROR: unsupported package manager" >&2; exit 1; fi
    else echo "  $pkg: OK"; fi
}
install_if_missing flatpak
install_if_missing flatpak-builder

# ── Flatpak remote + runtime ──────────────────────────────────────────────────
section "Configuring Flathub remote"
flatpak remote-add --if-not-exists --user flathub \
    https://dl.flathub.org/repo/flathub.flatpakrepo

section "Installing runtime and SDK (${RUNTIME_VERSION})"
flatpak install --user --noninteractive flathub \
    "${RUNTIME}//${RUNTIME_VERSION}" \
    "${SDK}//${RUNTIME_VERSION}" \
    || true

# ── Pre-download wheels (Python 3.13 / manylinux x86_64) ──────────────────────
# Downloading on the host avoids slow sandboxed network calls and lets the
# sandbox install with --no-index (fully offline build).  Dependencies are
# resolved here so PySide6's Essentials/Addons sub-wheels come along too.
section "Pre-downloading wheels (Python ${WHEEL_PYTHON} / ${WHEEL_PLATFORM})"
rm -rf .flatpak-wheels
mkdir -p .flatpak-wheels

run_with_spinner "Downloading wheels for $(grep -cE '^[^#[:space:]]' requirements.txt) requirements" -- \
    pip download --only-binary :all: \
        --python-version "${WHEEL_PYTHON}" --implementation cp \
        --platform "${WHEEL_PLATFORM}" \
        -q -d .flatpak-wheels -r requirements.txt

echo "  $(ls .flatpak-wheels/ | wc -l) distributions ready"

# ── Packaging helpers ─────────────────────────────────────────────────────────
section "Writing packaging helpers"
mkdir -p packaging

# site-packages path matches the runtime's Python version.  ClearBudget writes
# its data under ~/.clearbudget (see clear_budget/shared/config.py), which the
# --filesystem=home permission below makes writable, so no user-dirs override
# env var is needed.
cat > packaging/clearbudget-launcher.sh <<LAUNCHER
#!/bin/sh
export LD_LIBRARY_PATH="/app/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
export PYTHONPATH="/app/share/clearbudget:/app/lib/python${PYTHON_MM}/site-packages\${PYTHONPATH:+:\$PYTHONPATH}"
export QT_PLUGIN_PATH="/app/lib/python${PYTHON_MM}/site-packages/PySide6/Qt/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="/app/lib/python${PYTHON_MM}/site-packages/PySide6/Qt/plugins/platforms"
export QML2_IMPORT_PATH="/app/lib/python${PYTHON_MM}/site-packages/PySide6/Qt/qml"
if [ -n "\${WAYLAND_DISPLAY:-}" ] && [ -z "\${FORCE_X11:-}" ]; then
    export QT_QPA_PLATFORM=wayland
elif [ -n "\${DISPLAY:-}" ]; then
    export QT_QPA_PLATFORM=xcb
else
    export QT_QPA_PLATFORM=xcb
fi
exec python3 /app/share/clearbudget/main.py "\$@"
LAUNCHER
chmod +x packaging/clearbudget-launcher.sh

cat > "packaging/${APP_ID}.desktop" <<DESKTOP
[Desktop Entry]
Name=Clear Budget
Comment=Personal monthly budget planner with credit card tracking
Exec=clearbudget
Icon=${APP_ID}
Terminal=false
Type=Application
Categories=Office;Finance;
DESKTOP

cat > "packaging/${APP_ID}.metainfo.xml" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>${APP_ID}</id>
  <name>Clear Budget</name>
  <summary>Personal monthly budget planner with credit card tracking</summary>
  <metadata_license>MIT</metadata_license>
  <project_license>LGPL-3.0-only</project_license>
  <description>
    <p>Clear Budget is a local-first desktop budget planner.  It tracks monthly
    bills, income sources and credit card balances per user, with all data held
    in a private SQLite database on your own machine.</p>
  </description>
  <releases>
    <release version="${APP_VERSION}" date="$(date +%Y-%m-%d)"/>
  </releases>
  <url type="homepage">https://github.com/oernster/ClearBudget</url>
</component>
XML

echo "  Packaging helpers ready."

# ── Manifest ──────────────────────────────────────────────────────────────────
section "Writing manifest ${MANIFEST}"

cat > "${MANIFEST}" <<YAML
app-id: ${APP_ID}
runtime: ${RUNTIME}
runtime-version: "${RUNTIME_VERSION}"
sdk: ${SDK}

command: clearbudget

build-options:
  strip: true
  no-debuginfo: true

finish-args:
  - --share=ipc
  - --socket=fallback-x11
  - --socket=wayland
  - --device=dri
  # ClearBudget stores its databases under ~/.clearbudget and reads/writes
  # user-chosen files for import/export, so it needs home access.
  - --filesystem=home

modules:

  # ── Python dependencies (local wheels only, fully offline) ────────────────
  - name: python-deps
    buildsystem: simple
    build-commands:
      - python3 -m ensurepip --upgrade --default-pip
      - pip3 install --no-cache-dir --no-index --find-links wheels --prefix=/app
          -r requirements.txt
    sources:
      - type: dir
        path: .flatpak-wheels
        dest: wheels
      - type: file
        path: requirements.txt

  # ── ClearBudget application source ────────────────────────────────────────
  - name: clearbudget
    buildsystem: simple
    build-commands:
      - mkdir -p /app/share/clearbudget
      - cp main.py VERSION /app/share/clearbudget/
      - cp -r clear_budget /app/share/clearbudget/
      # main.py resolves its runtime tray/window icon as clearbudget_256.png
      # beside itself (see _find_runtime_icon), so stage it under that name.
      - cp ClearBudget_256.png /app/share/clearbudget/clearbudget_256.png
      - install -Dm644 ClearBudget_16.png  /app/share/icons/hicolor/16x16/apps/${APP_ID}.png
      - install -Dm644 ClearBudget_32.png  /app/share/icons/hicolor/32x32/apps/${APP_ID}.png
      - install -Dm644 ClearBudget_48.png  /app/share/icons/hicolor/48x48/apps/${APP_ID}.png
      - install -Dm644 ClearBudget_64.png  /app/share/icons/hicolor/64x64/apps/${APP_ID}.png
      - install -Dm644 ClearBudget_128.png /app/share/icons/hicolor/128x128/apps/${APP_ID}.png
      - install -Dm644 ClearBudget_256.png /app/share/icons/hicolor/256x256/apps/${APP_ID}.png
      - install -Dm644 ClearBudget_512.png /app/share/icons/hicolor/512x512/apps/${APP_ID}.png
      - install -Dm755 packaging/clearbudget-launcher.sh /app/bin/clearbudget
      - install -Dm644 packaging/${APP_ID}.desktop /app/share/applications/${APP_ID}.desktop
      - install -Dm644 packaging/${APP_ID}.metainfo.xml /app/share/metainfo/${APP_ID}.metainfo.xml
      - install -Dm644 LICENSE /app/share/licenses/${APP_ID}/LICENSE
    sources:
      - type: file
        path: main.py
      - type: file
        path: VERSION
      - type: file
        path: LICENSE
      - type: file
        path: ClearBudget_16.png
      - type: file
        path: ClearBudget_32.png
      - type: file
        path: ClearBudget_48.png
      - type: file
        path: ClearBudget_64.png
      - type: file
        path: ClearBudget_128.png
      - type: file
        path: ClearBudget_256.png
      - type: file
        path: ClearBudget_512.png
      - type: dir
        path: clear_budget
        dest: clear_budget
      - type: dir
        path: packaging
        dest: packaging
YAML

echo "  Manifest written."

# ── Build ─────────────────────────────────────────────────────────────────────
section "Building Flatpak"
rm -rf "${BUILD_DIR}" "${REPO_DIR}"

flatpak-builder \
    --user \
    --install-deps-from=flathub \
    --install \
    --force-clean \
    --repo="${REPO_DIR}" \
    "${BUILD_DIR}" \
    "${MANIFEST}"

# ── Bundle (on by default; skip with --no-bundle) ─────────────────────────────
if [[ $MAKE_BUNDLE -eq 1 ]]; then
    section "Bundling to ${BUNDLE}"
    echo "  The spinner shows how much of ${BUNDLE} has been written."
    echo
    rm -f "${BUNDLE}"
    run_with_spinner "Writing ${BUNDLE}" --watch "${BUNDLE}" -- \
        flatpak build-bundle "${REPO_DIR}" "${BUNDLE}" "${APP_ID}"
    echo
    echo "${bold}Bundle: ${BUNDLE}  ($(du -sh "${BUNDLE}" | cut -f1))${reset}"
    echo
    echo "Install on another machine:"
    echo "  1. Copy ${BUNDLE} to the target machine"
    echo "  2. flatpak install --user ${BUNDLE}"
    echo "  3. flatpak run ${APP_ID}"
fi

echo
echo "${bold}Build complete.${reset}"
echo
echo "The app is already installed locally.  To manage it:"
echo
echo "  Run:        flatpak run ${APP_ID}"
echo "  Uninstall:  flatpak uninstall --user ${APP_ID}"
echo
if [[ $MAKE_BUNDLE -ne 1 ]]; then
    echo "Bundle skipped (--no-bundle).  Run without it to produce ${BUNDLE}."
    echo
fi
