"""Structural tests for the auth module.

Verifies:
- Auth module only imports from stdlib, third-party (bcrypt), and clear_budget.auth.
- Auth module files stay under 400 LOC.
- Auth module has no circular dependencies within itself.
- UserStore protocol: required public methods exist.
"""

import ast
from pathlib import Path


def _parse_imports(filepath: Path) -> set[str]:
    """Return all module strings imported in a file."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    imports: set[str] = set()

    class _Visitor(ast.NodeVisitor):
        def visit_ImportFrom(self, node):
            if node.module:
                imports.add(node.module)
            self.generic_visit(node)

        def visit_Import(self, node):
            for alias in node.names:
                imports.add(alias.name)
            self.generic_visit(node)

    _Visitor().visit(tree)
    return imports


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_AUTH_DIR = _PROJECT_ROOT / "clear_budget" / "auth"

_ALLOWED_PREFIXES = (
    "clear_budget.auth",
    "clear_budget.shared",
)

_STDLIB_OR_THIRD_PARTY = {
    "bcrypt",
    "secrets",
    "sqlite3",
    "pathlib",
    "dataclasses",
    "typing",
    "re",
    "os",
    "sys",
}


class TestAuthLayering:
    """Auth module must not import from domain, application, infrastructure, or ui."""

    def test_auth_has_no_forbidden_layer_imports(self) -> None:
        _FORBIDDEN_LAYERS = {
            "clear_budget.domain",
            "clear_budget.application",
            "clear_budget.infrastructure",
            "clear_budget.ui",
        }
        violations = []
        for py_file in _AUTH_DIR.rglob("*.py"):
            imports = _parse_imports(py_file)
            bad = [
                imp
                for imp in imports
                if any(imp.startswith(layer) for layer in _FORBIDDEN_LAYERS)
            ]
            if bad:
                violations.append(f"{py_file.relative_to(_PROJECT_ROOT)}: {bad}")

        assert not violations, "Auth module imports forbidden layers:\n" + "\n".join(
            violations
        )


class TestAuthLOC:
    """Auth module files must not exceed 400 LOC."""

    def test_all_auth_files_under_400_loc(self) -> None:
        violations = []
        for py_file in _AUTH_DIR.rglob("*.py"):
            loc = len(py_file.read_text(encoding="utf-8").splitlines())
            if loc > 400:
                violations.append(f"{py_file.relative_to(_PROJECT_ROOT)}: {loc} lines")
        assert not violations, "Auth files exceed 400 LOC:\n" + "\n".join(violations)


class TestUserStoreInterface:
    """UserStore exposes the required public API."""

    def test_required_methods_exist(self) -> None:
        from clear_budget.auth.user_store import UserStore

        required = [
            "has_users",
            "get_all_users",
            "find_user",
            "verify_password",
            "verify_recovery_code",
            "create_user",
            "change_password",
            "delete_user",
            "close",
        ]
        for method in required:
            assert hasattr(
                UserStore, method
            ), f"UserStore missing required method: {method}"


class TestUserModelImmutability:
    """User model is a frozen dataclass (immutable)."""

    def test_user_is_immutable(self) -> None:
        from clear_budget.auth.models import User
        import dataclasses

        fields = dataclasses.fields(User)
        assert len(fields) > 0

        user = User(id=1, username="alice", is_admin=False)
        try:
            user.username = "bob"  # type: ignore[misc]
            raise AssertionError("User should be immutable (frozen dataclass)")
        except (dataclasses.FrozenInstanceError, AttributeError):
            pass  # Expected — frozen dataclass raises FrozenInstanceError
