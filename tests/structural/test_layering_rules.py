"""Structural tests for the layering rules: UI -> Application -> Domain <- Infrastructure.

Every import is resolved to the layer it lands in, whether it is written
absolutely (`from clear_budget.infrastructure.sqlite import x`), as a dotted
`import clear_budget.ui.views` or relatively (`from ..infrastructure import x`).

This file used to compare the names it collected (`clear_budget.infrastructure`)
against bare layer names (`infrastructure`), so no real import could ever
match: a domain module importing infrastructure was planted and passed. It also
carried two rules backwards for this codebase, forbidding the UI to import the
application layer and infrastructure to import an application port. The rules
below are the ones ARCHITECTURE.md documents and the code keeps:

- Domain imports no other layer but `shared`; nor any I/O, threading,
  network, logging or UI-framework module.
- Application never imports infrastructure or the UI.
- Infrastructure never imports the UI. It may import application ports and
  their DTOs, since it implements them (the update check's `ReleaseSource`).
- The UI never imports infrastructure, except `ui/window_builder.py`, the
  wiring for one budget split out of the composition root. The UI importing
  the domain directly is allowed for now; TECH_DEBT.md records it.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE = "clear_budget"

FORBIDDEN: dict[str, frozenset[str]] = {
    "domain": frozenset({"application", "infrastructure", "ui", "auth", "version"}),
    "application": frozenset({"infrastructure", "ui"}),
    "infrastructure": frozenset({"ui"}),
    "ui": frozenset({"infrastructure"}),
}

# What a pure domain may not reach for: I/O, processes, threads, the network,
# logging and the UI framework. Matched on the top-level module name.
DOMAIN_IMPURE = frozenset(
    {
        "os",
        "io",
        "pathlib",
        "shutil",
        "tempfile",
        "sqlite3",
        "subprocess",
        "threading",
        "asyncio",
        "socket",
        "http",
        "urllib",
        "logging",
        "PySide6",
    }
)

# Files allowed one forbidden edge, each with the layer it may reach and why.
WIRING_EXEMPTIONS: dict[str, str] = {
    "clear_budget/ui/window_builder.py": "infrastructure",
}


def imported_modules(path: Path, root: Path = _ROOT) -> set[str]:
    """Every module `path` imports, by full dotted name, relative ones resolved."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    package = list(path.relative_to(root).parent.parts)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)]
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


def layer_of(module: str) -> str | None:
    """The layer a dotted module belongs to; None outside the package."""
    parts = module.split(".")
    if parts[0] != _PACKAGE or len(parts) < 2:
        return None
    return parts[1]


def violations(layer: str) -> list[str]:
    forbidden = FORBIDDEN[layer]
    found = []
    for path in sorted((_ROOT / _PACKAGE / layer).rglob("*.py")):
        rel = path.relative_to(_ROOT).as_posix()
        allowed = WIRING_EXEMPTIONS.get(rel)
        for module in sorted(imported_modules(path)):
            target = layer_of(module)
            if target in forbidden and target != allowed:
                found.append(f"{rel} imports {module}")
    return found


class TestLayeringRules:
    """Each layer imports only what the architecture lets it."""

    def test_domain_has_no_forbidden_imports(self):
        assert violations("domain") == []

    def test_application_has_no_forbidden_imports(self):
        assert violations("application") == []

    def test_infrastructure_has_no_forbidden_imports(self):
        assert violations("infrastructure") == []

    def test_ui_has_no_forbidden_imports(self):
        assert violations("ui") == []

    def test_domain_is_free_of_io_and_frameworks(self):
        found = [
            f"{path.relative_to(_ROOT).as_posix()} imports {module}"
            for path in sorted((_ROOT / _PACKAGE / "domain").rglob("*.py"))
            for module in sorted(imported_modules(path))
            if module.split(".")[0] in DOMAIN_IMPURE
        ]
        assert found == []


class TestTheExemptions:
    """An exemption names a file that exists and still needs it, so it can
    neither point at nothing nor outlive its reason."""

    def test_each_exempt_file_still_reaches_the_layer_it_is_allowed(self):
        for rel, allowed in WIRING_EXEMPTIONS.items():
            reached = {layer_of(m) for m in imported_modules(_ROOT / rel)}
            assert allowed in reached, rel


class TestTheResolution:
    """The scan is only as good as its reading of an import, which is what
    the old version got wrong; each way of writing one is pinned."""

    def _imports(self, tmp_path: Path, source: str) -> set[str]:
        module = tmp_path / _PACKAGE / "domain" / "services" / "probe.py"
        module.parent.mkdir(parents=True)
        module.write_text(source, encoding="utf-8")
        return {layer_of(m) for m in imported_modules(module, tmp_path)}

    def test_an_absolute_import_is_resolved(self, tmp_path):
        layers = self._imports(
            tmp_path, "from clear_budget.infrastructure.x import y\n"
        )
        assert "infrastructure" in layers

    def test_a_dotted_import_is_resolved(self, tmp_path):
        assert "ui" in self._imports(tmp_path, "import clear_budget.ui.views\n")

    def test_a_relative_import_is_resolved(self, tmp_path):
        assert "application" in self._imports(
            tmp_path, "from ...application.services import z\n"
        )

    def test_a_relative_import_inside_the_layer_stays_there(self, tmp_path):
        assert self._imports(tmp_path, "from .sibling import z\n") == {"domain"}

    def test_a_third_party_import_belongs_to_no_layer(self, tmp_path):
        assert self._imports(tmp_path, "import json\nfrom PySide6 import QtGui\n") == {
            None
        }
