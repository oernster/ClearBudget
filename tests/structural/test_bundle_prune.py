"""The packaging prune never names anything the application loads.

`build_prune.py` lists the Qt modules, plugins and Python packages every
delivery script leaves out of a bundle. That list is only safe while the
application imports none of them; nothing in a build would say otherwise:
a pruned module fails at runtime, on the user's machine, with the build
reporting success. So the two are held together here by source scan, the
same way the delivery-asset lists are.

The second half pins the rules themselves against the file names PySide6
uses on each platform, because the macOS and Linux layouts cannot be built on
the machine that writes the rules: a rule that misses a name leaves bytes
behind, which is harmless; a rule that matches a name it must not would take
the window with it, which is not.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import build_prune

_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_DIRS = (_ROOT / "clear_budget", _ROOT / "installer")
_SOURCE_FILES = (_ROOT / "main.py",)


def _sources() -> list[Path]:
    files = list(_SOURCE_FILES)
    for folder in _SOURCE_DIRS:
        files.extend(p for p in folder.rglob("*.py") if "__pycache__" not in p.parts)
    return files


def _imported_modules() -> set[str]:
    """Every dotted module name the application imports, at any depth."""
    names: set[str] = set()
    for path in _sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
                names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _qt_modules_imported() -> set[str]:
    prefix = "PySide6.Qt"
    return {
        name[len("PySide6.") :].split(".")[0]
        for name in _imported_modules()
        if name.startswith(prefix)
    }


class TestTheApplicationImportsOnlyWhatShips:
    def test_no_imported_qt_module_is_pruned(self) -> None:
        pruned = {
            module
            for module in _qt_modules_imported()
            if build_prune.is_unused_qt_module(module[len("Qt") :])
        }
        assert not pruned, (
            f"the application imports {sorted(pruned)} but build_prune drops"
            " them from every bundle; remove them from"
            " UNUSED_QT_MODULE_PREFIXES or stop importing them"
        )

    def test_no_excluded_python_module_is_imported(self) -> None:
        imported = _imported_modules()
        clashes = sorted(
            excluded
            for excluded in build_prune.EXCLUDED_MODULES
            if any(
                name == excluded or name.startswith(excluded + ".") for name in imported
            )
        )
        assert not clashes, (
            f"{clashes} are passed to PyInstaller as --exclude-module but the"
            " application imports them"
        )

    def test_the_scan_sees_the_qt_the_application_uses(self) -> None:
        """Worthless if the import walk returned nothing."""
        assert {"QtCore", "QtGui", "QtWidgets"} <= _qt_modules_imported()


@pytest.mark.parametrize(
    "path",
    [
        # Windows, as PyInstaller lays the folder out.
        "_internal/PySide6/Qt6Quick.dll",
        "_internal/PySide6/QtQuick.pyd",
        "_internal/PySide6/QtNetwork.pyd",
        "_internal/PySide6/Qt6Pdf.dll",
        "_internal/PySide6/Qt6Svg.dll",
        "_internal/PySide6/Qt6VirtualKeyboard.dll",
        "_internal/PySide6/opengl32sw.dll",
        "_internal/PySide6/translations/qt_gl.qm",
        "_internal/PySide6/plugins/tls/qopensslbackend.dll",
        "_internal/PySide6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll",
        "_internal/PySide6/plugins/imageformats/qjpeg.dll",
        "_internal/PySide6/plugins/iconengines/qsvgicon.dll",
        "_internal/PySide6/plugins/platforms/qdirect2d.dll",
        # macOS, inside the .app.
        "Contents/Frameworks/PySide6/Qt/lib/QtQuick.framework",
        "Contents/Frameworks/PySide6/Qt/lib/QtQml.framework/Versions/A/QtQml",
        "Contents/Frameworks/PySide6/Qt/plugins/imageformats/libqjpeg.dylib",
        "Contents/Frameworks/PySide6/Qt/translations",
        "Contents/Frameworks/PySide6/QtQuick.abi3.so",
        # Linux, in the Flatpak's site-packages (the PySide6 directory is the
        # pruned root there; prune_tree keeps its name in front).
        "PySide6/Qt/lib/libQt6Quick.so.6.11.1",
        "PySide6/Qt/lib/libQt6Network.so.6",
        "PySide6/Qt/plugins/imageformats/libqjpeg.so",
        "PySide6/Qt/qml",
        "PySide6/include",
        "PySide6/designer",
        "PySide6/QtQuick.pyi",
    ],
)
def test_what_is_never_loaded_is_pruned(path: str) -> None:
    assert build_prune.should_prune(path), f"{path} should be pruned"


@pytest.mark.parametrize(
    "path",
    [
        # Windows.
        "_internal/PySide6/Qt6Core.dll",
        "_internal/PySide6/Qt6Gui.dll",
        "_internal/PySide6/Qt6Widgets.dll",
        "_internal/PySide6/QtCore.pyd",
        "_internal/PySide6/QtGui.pyi",
        "_internal/PySide6/pyside6.abi3.dll",
        "_internal/PySide6/plugins/platforms/qwindows.dll",
        "_internal/PySide6/plugins/styles/qmodernwindowsstyle.dll",
        "_internal/PySide6/plugins/imageformats/qico.dll",
        "_internal/shiboken6/Shiboken.pyd",
        "_internal/python313.dll",
        "_internal/libcrypto-3.dll",
        "_internal/clear_budget/ui/theme.py",
        "_internal/ClearBudget_256.png",
        # macOS.
        "Contents/Frameworks/PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore",
        "Contents/Frameworks/PySide6/Qt/plugins/platforms/libqcocoa.dylib",
        "Contents/Frameworks/PySide6/Qt/plugins/styles/libqmacstyle.dylib",
        # Linux: the window, the Wayland and X11 plugins and what they link.
        "PySide6/Qt/lib/libQt6DBus.so.6",
        "PySide6/Qt/lib/libQt6XcbQpa.so.6",
        "PySide6/Qt/lib/libQt6WaylandClient.so.6",
        "PySide6/Qt/lib/libQt6OpenGL.so.6",
        "PySide6/Qt/lib/libQt6EglFSDeviceIntegration.so.6",
        "PySide6/Qt/lib/libicuuc.so.73",
        "PySide6/Qt/plugins/platforms/libqxcb.so",
        "PySide6/Qt/plugins/platforms/libqwayland-generic.so",
        "PySide6/Qt/plugins/platformthemes/libqgtk3.so",
        "PySide6/Qt/plugins/wayland-shell-integration/libxdg-shell.so",
        "PySide6/Qt/plugins/xcbglintegrations/libqxcb-glx-integration.so",
        "PySide6/__init__.py",
        "PySide6/QtWidgets.abi3.so",
    ],
)
def test_what_the_window_needs_is_kept(path: str) -> None:
    assert not build_prune.should_prune(path), f"{path} must be kept"
