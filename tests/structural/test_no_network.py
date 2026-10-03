"""The update check is the only connection ClearBudget opens itself.

DECISIONS-TRADEOFFS.md and ARCHITECTURE.md say so; until this file nothing
held it, so a new outbound call would have compiled, passed and shipped. The
claim is about everything a user installs, so the scan covers the package,
the setup program and the composition root. The delivery scripts never reach
a user's machine and are left out.

The one exemption is the update check's GitHub adapter. It is asserted whole:
the module must exist, must still need its exemption and may import nothing
networked beyond what the exemption grants, so the hole can neither widen nor
outlive its purpose. The donate button and an offered download hand an
address to the browser through Qt and open no connection here.

What this cannot see: a connection opened by a library through a module not
listed below. It reads source, not the frozen build.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SHIPPED_PACKAGES = ("clear_budget", "installer")
_SHIPPED_FILES = ("main.py",)
# Build output and delivery scripts sit inside a shipped package's folder but
# are not themselves shipped as source.
_NOT_SHIPPED_DIRS = {"payload", "__pycache__"}
_DELIVERY_SCRIPTS = {"installer/build_payload.py"}

FORBIDDEN_NETWORK_ROOTS = {
    "socket",
    "ssl",
    "http",
    "smtplib",
    "imaplib",
    "poplib",
    "ftplib",
    "telnetlib",
    "xmlrpc",
    "requests",
    "httpx",
    "aiohttp",
    "urllib3",
    "websocket",
    "websockets",
}
# Matched as prefixes: the Qt names cover every WebEngine module at once.
FORBIDDEN_NETWORK_PREFIXES = (
    "urllib.request",
    "urllib.error",
    "PySide6.QtNetwork",
    "PySide6.QtWebEngine",
    "PySide6.QtWebSockets",
)

UPDATE_CHECK_EXEMPT_MODULE = (
    "clear_budget/infrastructure/update/github_release_source.py"
)
UPDATE_CHECK_ALLOWED_IMPORTS = {"urllib.request"}


def _relative(path: Path) -> str:
    return path.relative_to(_ROOT).as_posix()


def iter_shipped_modules() -> list[Path]:
    paths = [_ROOT / name for name in _SHIPPED_FILES]
    for package in _SHIPPED_PACKAGES:
        for path in sorted((_ROOT / package).rglob("*.py")):
            if _NOT_SHIPPED_DIRS.intersection(path.relative_to(_ROOT).parts):
                continue
            if _relative(path) in _DELIVERY_SCRIPTS:
                continue
            paths.append(path)
    return paths


def imports_of(path: Path) -> set[str]:
    """Every module `path` imports, by its full dotted name.

    `from a import b` records both `a` and `a.b`, because `b` may be a
    submodule: `from PySide6 import QtNetwork` is an import of
    `PySide6.QtNetwork` and has to be seen as one.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def is_network_module(module: str) -> bool:
    return module.split(".")[0] in FORBIDDEN_NETWORK_ROOTS or module.startswith(
        FORBIDDEN_NETWORK_PREFIXES
    )


def _network_imports_of(path: Path) -> list[str]:
    return sorted(m for m in imports_of(path) if is_network_module(m))


def _exempt_module() -> Path:
    for path in iter_shipped_modules():
        if _relative(path) == UPDATE_CHECK_EXEMPT_MODULE:
            return path
    raise AssertionError("exempt module not found in the scan")


class TestNoNetwork:
    def test_no_shipped_module_but_the_update_check_imports_networking(self) -> None:
        problems = [
            f"{_relative(path)} imports {module}"
            for path in iter_shipped_modules()
            if _relative(path) != UPDATE_CHECK_EXEMPT_MODULE
            for module in _network_imports_of(path)
        ]
        assert problems == []


class TestUpdateCheckExemption:
    """The exemption is a claim about one module, so it is asserted whole."""

    def test_the_exemption_has_not_outlived_its_reason(self) -> None:
        assert UPDATE_CHECK_ALLOWED_IMPORTS <= imports_of(_exempt_module())

    def test_the_exemption_grants_nothing_beyond_its_purpose(self) -> None:
        extras = [
            module
            for module in _network_imports_of(_exempt_module())
            if module not in UPDATE_CHECK_ALLOWED_IMPORTS
        ]
        assert extras == []


class TestTheRecognition:
    def test_network_modules_are_recognised(self) -> None:
        for module in (
            "socket",
            "http.client",
            "urllib.request",
            "urllib.error",
            "requests.adapters",
            "PySide6.QtNetwork",
            "PySide6.QtWebEngineWidgets",
            "PySide6.QtWebSockets",
        ):
            assert is_network_module(module), module

    def test_ordinary_modules_are_not(self) -> None:
        for module in (
            "urllib.parse",
            "json",
            "socketserverless",
            "httpie_free",
            "PySide6.QtWidgets",
            "PySide6.QtGui",
        ):
            assert not is_network_module(module), module

    def test_a_submodule_imported_from_its_package_is_seen(self, tmp_path) -> None:
        source = tmp_path / "probe.py"
        source.write_text(
            "from PySide6 import QtNetwork\nfrom urllib import request\n"
            "from . import sibling\n",
            encoding="utf-8",
        )
        found = imports_of(source)
        assert {"PySide6.QtNetwork", "urllib.request"} <= found
        assert not any(name.endswith("sibling") for name in found)


class TestScopeOfTheClaim:
    """The invariant is only as good as the surface it is proven over, so the
    surface is asserted rather than assumed. Narrowing the scan back to the
    package has to fail here rather than pass quietly."""

    def test_the_scan_reaches_beyond_the_package(self) -> None:
        scanned = {_relative(path) for path in iter_shipped_modules()}
        assert "main.py" in scanned
        assert "installer/app.py" in scanned
        assert any(name.startswith("clear_budget/") for name in scanned)

    def test_delivery_scripts_and_build_output_are_not_scanned(self) -> None:
        scanned = {_relative(path) for path in iter_shipped_modules()}
        assert scanned.isdisjoint(_DELIVERY_SCRIPTS)
        assert not any("payload" in name.split("/") for name in scanned)

    def test_every_named_exclusion_exists(self) -> None:
        for script in _DELIVERY_SCRIPTS:
            assert (_ROOT / script).is_file(), script
