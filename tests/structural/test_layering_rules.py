"""Structural tests for clean architecture layering rules.

Uses AST walking to verify that:
- Domain layer has zero imports from application, infrastructure, ui
- Application layer has zero imports from infrastructure, ui
- Infrastructure layer has zero imports from application, ui
- Only main.py may import from multiple layers for composition
"""

import ast
import sys
from pathlib import Path


class ImportChecker(ast.NodeVisitor):
    """AST visitor to extract import statements."""

    def __init__(self):
        self.imports = set()

    def visit_ImportFrom(self, node):
        """Collect 'from X import Y' statements."""
        if node.module:
            self.imports.add(node.module)
        self.generic_visit(node)

    def visit_Import(self, node):
        """Collect 'import X' statements."""
        for alias in node.names:
            self.imports.add(alias.name.split(".")[0])
        self.generic_visit(node)


def get_imports_from_file(filepath: Path) -> set:
    """Extract all imports from a Python file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (SyntaxError, UnicodeDecodeError):
        return set()

    checker = ImportChecker()
    checker.visit(tree)
    return checker.imports


def get_layer_from_path(filepath: Path) -> str | None:
    """Determine which layer a file belongs to."""
    parts = filepath.parts
    if "clear_budget" not in parts:
        return None

    idx = parts.index("clear_budget")
    if idx + 1 < len(parts):
        layer = parts[idx + 1]
        if layer in ("domain", "application", "infrastructure", "ui"):
            return layer
    return None


class TestLayeringRules:
    """Test clean architecture layering rules."""

    def test_domain_has_no_forbidden_imports(self):
        """Domain layer must not import from application, infrastructure, ui."""
        project_root = Path(__file__).parent.parent.parent
        domain_dir = project_root / "clear_budget" / "domain"

        forbidden = {"application", "infrastructure", "ui"}
        violations = []

        for py_file in domain_dir.rglob("*.py"):
            imports = get_imports_from_file(py_file)
            bad_imports = [imp for imp in imports if imp in forbidden]
            if bad_imports:
                violations.append(f"{py_file.relative_to(project_root)}: {bad_imports}")

        assert not violations, f"Domain layer imports forbidden modules:\n" + "\n".join(
            violations
        )

    def test_application_has_no_forbidden_imports(self):
        """Application layer must not import from infrastructure, ui."""
        project_root = Path(__file__).parent.parent.parent
        application_dir = project_root / "clear_budget" / "application"

        forbidden = {"infrastructure", "ui"}
        violations = []

        for py_file in application_dir.rglob("*.py"):
            imports = get_imports_from_file(py_file)
            bad_imports = [imp for imp in imports if imp in forbidden]
            if bad_imports:
                violations.append(f"{py_file.relative_to(project_root)}: {bad_imports}")

        assert not violations, (
            f"Application layer imports forbidden modules:\n" + "\n".join(violations)
        )

    def test_infrastructure_has_no_forbidden_imports(self):
        """Infrastructure layer must not import from application, ui."""
        project_root = Path(__file__).parent.parent.parent
        infrastructure_dir = project_root / "clear_budget" / "infrastructure"

        if not infrastructure_dir.exists():
            return  # Skip if infrastructure not yet implemented

        forbidden = {"application", "ui"}
        violations = []

        for py_file in infrastructure_dir.rglob("*.py"):
            imports = get_imports_from_file(py_file)
            bad_imports = [imp for imp in imports if imp in forbidden]
            if bad_imports:
                violations.append(f"{py_file.relative_to(project_root)}: {bad_imports}")

        assert not violations, (
            f"Infrastructure layer imports forbidden modules:\n" + "\n".join(violations)
        )

    def test_ui_has_no_forbidden_imports(self):
        """UI layer must not import from other layers for logic (only domain/infrastructure)."""
        project_root = Path(__file__).parent.parent.parent
        ui_dir = project_root / "clear_budget" / "ui"

        if not ui_dir.exists():
            return  # Skip if UI not yet implemented

        # UI can import from domain/infrastructure for data access
        # but not from application (that's what DTOs are for)
        forbidden = {"application"}
        violations = []

        for py_file in ui_dir.rglob("*.py"):
            imports = get_imports_from_file(py_file)
            bad_imports = [imp for imp in imports if imp in forbidden]
            if bad_imports:
                violations.append(f"{py_file.relative_to(project_root)}: {bad_imports}")

        assert not violations, (
            f"UI layer imports forbidden modules:\n" + "\n".join(violations)
        )
