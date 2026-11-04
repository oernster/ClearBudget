"""What PySide6 ships that ClearBudget never loads; how to leave it out.

ClearBudget imports QtCore, QtGui and QtWidgets and nothing else from Qt
(`tests/structural/test_bundle_prune.py` holds that true). PyInstaller cannot
know that: its Qt hooks collect every plugin directory a module might use;
each plugin drags its own libraries in behind it. Measured on 2026-11-04, the
Windows bundle carried a 20 MB software OpenGL renderer, the whole Qt Quick
and Qml stack (pulled in by the virtual keyboard input plugin), Qt Pdf (pulled
in by a PDF image format plugin), Qt Network with three TLS backends plus two
OpenSSL libraries lifted out of C:\\Windows\\System32 and 7 MB of Qt
translations the application never installs. None of it is reachable from a
widgets application that draws PNG pictures and reads an ICO.

The rules live here, once. They are applied three ways:

* `prune_tree` walks a finished bundle and deletes what matches: the Windows
  onedir folder (`buildexe.py`), the macOS .app (`builddmg.py`) and the
  Flatpak's site-packages (`build_flatpak.sh`).
* `should_prune` filters PyInstaller's binaries and datas inside the generated
  spec for the single-file setup program (`buildinstaller.py`), where there
  is no folder to walk afterwards.
* `EXCLUDED_MODULES` is passed to PyInstaller as `--exclude-module` so the
  Python side stays out too: keyring's own test package imports pytest;
  collecting all of keyring brought pytest, pluggy and pygments along.

Every rule is written against the file NAMES PySide6 uses on all three
platforms (`Qt6Quick.dll`, `QtQuick.framework`, `libQt6Quick.so.6`,
`QtQuick.abi3.so`, `QtQuick.pyd`, `QtQuick.pyi`), so one list serves the
Windows, macOS and Linux layouts. A rule that misses leaves bytes behind; it
cannot break the application, because nothing here names a module the
application imports. `verify_no_dangling_imports` proves that on Windows after
the prune, by reading the import table of every binary left.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

# Qt modules the application never imports. A name here drops the Qt library,
# the Python binding, its stub and (on macOS) the framework directory. Prefixes
# catch the families (Qt Quick alone is a dozen libraries). Qt Svg itself is
# kept: the GNOME Wayland decoration plugin (`libadwaita.so`) links it, so
# without it the window opens with no title bar. Only Svg Widgets goes.
UNUSED_QT_MODULE_PREFIXES = (
    "Concurrent",
    "Designer",
    "Help",
    "Labs",
    "Network",
    "OpenGLWidgets",
    "Pdf",
    "PrintSupport",
    "Qml",
    "Quick",
    "ShaderTools",
    "Sql",
    "SvgWidgets",
    "Test",
    "UiTools",
    "VirtualKeyboard",
    "Xml",
)

# Plugin directories under PySide6/plugins (Windows) or PySide6/Qt/plugins
# (macOS, Linux). The platform, style, theme and Wayland directories are not
# here, so a platform this build cannot test keeps its window.
UNUSED_PLUGIN_DIRS = frozenset(
    {
        "assetimporters",
        "canbus",
        "designer",
        "generic",
        "geometryloaders",
        "help",
        "iconengines",
        "multimedia",
        "networkinformation",
        "position",
        "printsupport",
        "qmllint",
        "qmltooling",
        "renderers",
        "sceneparsers",
        "scenegraph",
        "sensors",
        "sqldrivers",
        "texttospeech",
        "tls",
        "webview",
    }
)

# Image format plugins. PNG decoding is built into Qt Gui. ICO stays because the
# window icon on Windows is `ClearBudget.ico`, deployed beside the exe by the
# setup program and read through `find_qt_window_icon_path`.
UNUSED_IMAGE_FORMATS = frozenset(
    {"qgif", "qicns", "qjpeg", "qpdf", "qsvg", "qtga", "qtiff", "qwbmp", "qwebp"}
)

# Input method plugins. The virtual keyboard drags the whole Qt Quick and Qml
# stack in behind it. The ibus and compose plugins stay: Ubuntu GNOME sets
# QT_IM_MODULE=ibus and the Flatpak inherits it, so without them dead keys and
# input methods stop working.
UNUSED_INPUT_CONTEXTS = frozenset({"qtvirtualkeyboardplugin"})

# Platform plugins no desktop session loads. qwindows, qcocoa, qxcb and the
# Wayland plugins are not here.
UNUSED_PLATFORMS = frozenset(
    {"qdirect2d", "qlinuxfb", "qminimal", "qminimalegl", "qoffscreen", "qvnc"}
)

# Directories directly under PySide6 (under PySide6/Qt on macOS and Linux).
# The translations are Qt's own; the application installs no QTranslator.
UNUSED_DIRS = frozenset(
    {
        "examples",
        "glue",
        "include",
        "libexec",
        "metatypes",
        "mkspecs",
        "qml",
        "sbom",
        "translations",
        "typesystems",
    }
)

# Developer tools pip installs beside the bindings. PyInstaller never collects
# them; the Flatpak's site-packages has them all.
UNUSED_TOOLS = frozenset(
    {
        "assistant",
        "balsam",
        "balsamui",
        "designer",
        "linguist",
        "lrelease",
        "lupdate",
        "qml",
        "qmlcachegen",
        "qmlformat",
        "qmlimportscanner",
        "qmllint",
        "qmlls",
        "qmltyperegistrar",
        "qsb",
        "rcc",
        "svgtoqml",
        "uic",
    }
)

# Single files by name. The software OpenGL renderer is loaded only when a GL
# context is wanted and none can be had; a raster widgets application never
# asks for one.
UNUSED_FILES = frozenset({"opengl32sw.dll"})

# Python packages PyInstaller must leave out. QtNetwork is in this list as well
# as above because its hook is what collects the TLS plugins, which bring in
# whatever OpenSSL it finds on the build machine's PATH.
EXCLUDED_MODULES = (
    "PySide6.QtNetwork",
    "keyring.testing",
    "pytest",
    "_pytest",
    "pluggy",
    "pygments",
)

_QT_LIBRARY = re.compile(
    r"^(?:lib)?Qt6?([A-Za-z0-9]+?)"
    r"(?:\.framework|\.dll|\.pyd|\.pyi|\.prl|\.lib|\.abi3\.so"
    r"|\.so(?:\.\d+)*|(?:\.\d+)*\.dylib)$"
)

_PYSIDE_DIRS = ("PySide6", "Qt")


def _qt_module(name: str) -> str | None:
    """The Qt module a library, binding, stub or framework name belongs to."""
    match = _QT_LIBRARY.match(name)
    return match.group(1) if match else None


def is_unused_qt_module(module: str) -> bool:
    """Whether `module` (as in `PySide6.Qt<module>`) is dropped from a bundle."""
    return module.startswith(UNUSED_QT_MODULE_PREFIXES)


def _plugin_stem(name: str) -> str:
    """`libqjpeg.so` and `qjpeg.dll` both answer `qjpeg`."""
    stem = name.split(".")[0]
    return stem[len("lib") :] if stem.startswith("lib") else stem


def should_prune(path: str | Path) -> bool:
    """Whether a path inside a bundle is something the application never loads.

    Judged on names and their parents alone, so the same answer comes back for
    `_internal/PySide6/Qt6Quick.dll`, `Contents/Frameworks/PySide6/Qt/lib/
    QtQuick.framework` and `site-packages/PySide6/Qt/lib/libQt6Quick.so.6`.
    """
    parts = Path(str(path).replace("\\", "/")).parts
    for index, name in enumerate(parts):
        parent = parts[index - 1] if index else ""
        if name in UNUSED_FILES:
            return True
        module = _qt_module(name)
        if module is not None and is_unused_qt_module(module):
            return True
        if parent == "plugins" and name in UNUSED_PLUGIN_DIRS:
            return True
        if parent == "imageformats" and _plugin_stem(name) in UNUSED_IMAGE_FORMATS:
            return True
        is_input_context = parent == "platforminputcontexts"
        if is_input_context and _plugin_stem(name) in UNUSED_INPUT_CONTEXTS:
            return True
        if parent == "platforms" and _plugin_stem(name) in UNUSED_PLATFORMS:
            return True
        if parent in _PYSIDE_DIRS and name in UNUSED_DIRS:
            return True
        # A tool is a bare executable (Linux, macOS) or an .exe (Windows) sitting
        # directly in PySide6; the dotted forms are libraries judged above.
        is_executable_name = name == _plugin_stem(name) or name.endswith(".exe")
        if parent == "PySide6" and is_executable_name:
            if _plugin_stem(name) in UNUSED_TOOLS:
                return True
    return False


def _size_of(path: Path) -> int:
    if path.is_symlink() or path.is_file():
        return path.lstat().st_size
    return sum(p.lstat().st_size for p in path.rglob("*") if not p.is_dir())


def prune_tree(root: Path) -> tuple[list[str], int]:
    """Delete everything under `root` that `should_prune` names.

    Returns the relative paths removed and the bytes they held. Directories go
    whole, so a pruned framework or plugin directory is one entry. A symlink
    left pointing into something pruned goes too; see `_unlink_orphaned_links`.
    """
    removed: list[str] = []
    gone: list[Path] = []
    freed = 0
    # Judged with the root's own name in front, so the rules see it: the
    # Flatpak hands over the PySide6 directory itself, where `include` or
    # `designer` are only pruned as children of PySide6.
    root_name = root.resolve().name
    for path in sorted(root.rglob("*")):
        if not path.exists() and not path.is_symlink():
            continue  # inside a directory already removed
        rel = Path(root_name) / path.relative_to(root)
        if not should_prune(rel):
            continue
        freed += _size_of(path)
        # The entry itself, not what a symlink points at.
        gone.append(path.parent.resolve() / path.name)
        if path.is_symlink() or path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)
        removed.append(path.relative_to(root).as_posix())
    orphans, orphan_bytes = _unlink_orphaned_links(root, gone)
    return removed + orphans, freed + orphan_bytes


def _unlink_orphaned_links(root: Path, gone: list[Path]) -> tuple[list[str], int]:
    """Delete the symlinks under `root` that now point into a pruned entry.

    PyInstaller's .app carries a bare-named link per framework in both
    `Contents/Frameworks` and `Contents/Resources` (`QtQuick -> PySide6/Qt/
    lib/QtQuick.framework/Versions/A/QtQuick`). The name has no suffix, so no
    rule matches it; once the framework is pruned the link dangles and
    `codesign --verify --strict` rejects the whole bundle with "No such file
    or directory". Judged by where the link points rather than by its name,
    so a link the prune did not orphan is left alone.
    """
    removed: list[str] = []
    freed = 0
    for link in sorted(root.rglob("*")):
        if not link.is_symlink() or link.exists():
            continue
        target = link.resolve()
        if any(target.is_relative_to(entry) for entry in gone):
            freed += link.lstat().st_size
            link.unlink()
            removed.append(link.relative_to(root).as_posix())
    return removed, freed


def verify_no_dangling_imports(root: Path, removed: list[str]) -> list[str]:
    """Binaries left under `root` that import a DLL the prune removed.

    Windows only: it reads PE import tables through `pefile`, a build
    dependency. Elsewhere it answers an empty list and says so, because a
    check that was not run must not read as a pass.
    """
    try:
        import pefile
    except ImportError:
        print("  import check skipped: pefile is not installed on this platform")
        return []
    gone = {Path(entry).name.lower() for entry in removed}
    dangling: list[str] = []
    scanned = 0
    for binary in sorted(root.rglob("*")):
        if binary.suffix.lower() not in (".dll", ".pyd", ".exe"):
            continue
        try:
            pe = pefile.PE(str(binary), fast_load=True)
            pe.parse_data_directories(
                directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
            )
        except pefile.PEFormatError:
            continue
        scanned += 1
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            dll = entry.dll.decode(errors="replace").lower()
            if dll in gone:
                dangling.append(f"{binary.relative_to(root).as_posix()} -> {dll}")
        pe.close()
    if scanned:
        print(f"  import check: {scanned} binaries read, {len(dangling)} dangling")
    else:
        print("  import check skipped: no Windows binaries here")
    return dangling


def prune_and_verify(root: Path) -> None:
    """Prune `root`, report what went and fail if anything left needs it."""
    before = _size_of(root)
    removed, freed = prune_tree(root)
    print(
        f"  Pruned {len(removed)} entries, {freed / (1024 * 1024):.1f} MB:"
        f" {before / (1024 * 1024):.1f} MB -> "
        f"{(before - freed) / (1024 * 1024):.1f} MB"
    )
    dangling = verify_no_dangling_imports(root, removed)
    if dangling:
        raise SystemExit(
            "pruned a library something left behind still imports:\n  "
            + "\n  ".join(dangling)
        )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: build_prune.py <bundle or site-packages directory>")
        return 2
    root = Path(argv[1])
    if not root.is_dir():
        print(f"not a directory: {root}")
        return 1
    prune_and_verify(root)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
