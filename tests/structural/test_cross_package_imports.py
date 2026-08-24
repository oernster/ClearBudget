"""Every name one package imports from another must actually be there.

The setup program is a SECOND application built from this tree. It borrows a
handful of names from the application (the palette, the theme tokens, the
theme toggle's face and tooltip) so that the two never disagree in front of a
user who has just watched one hand over to the other. Nothing in the suite
imports its UI, because that half is omitted from coverage and needs Qt, so a
rename in the application could pass every gate here and break the setup
program on first launch. It did: `toggle_glyph` became `toggle_icon` when the
toggle's faces became pictures; the first anyone knew was an ImportError from
a built installer.

A source scan rather than an import: importing the installer's UI means
importing Qt into a suite that is deliberately Qt-free (tests/conftest.py).
The AST is enough to answer the question that matters, which is whether the
name being imported is defined in the module it is being taken from.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
# The packages whose imports are checked, plus the one they may borrow from.
_IMPORTING = ("installer", "clear_budget")
_PROVIDER = "clear_budget"


def _defined_names(module_path: Path) -> set[str]:
    """Every name `module_path` defines or re-exports at module level."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            # A re-export counts: several modules exist to widen another's
            # surface without moving a call site.
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def _module_file(dotted: str) -> Path | None:
    """The file backing `dotted`, else None when it is a package or absent."""
    as_module = _ROOT / Path(*dotted.split(".")).with_suffix(".py")
    if as_module.is_file():
        return as_module
    as_package = _ROOT / Path(*dotted.split(".")) / "__init__.py"
    return as_package if as_package.is_file() else None


def _borrowed() -> list[tuple[Path, int, str, str]]:
    """Every (file, line, module, name) imported from the provider package."""
    found: list[tuple[Path, int, str, str]] = []
    for package in _IMPORTING:
        for path in sorted((_ROOT / package).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.level:
                    continue
                if not node.module or not node.module.startswith(_PROVIDER + "."):
                    continue
                for alias in node.names:
                    if alias.name != "*":
                        found.append((path, node.lineno, node.module, alias.name))
    return found


def test_the_scan_finds_the_imports_it_is_meant_to_check() -> None:
    """Worthless if the packages stop borrowing from each other."""
    borrowed = _borrowed()
    assert borrowed, "no cross-package imports found, so this guard checks nothing"
    assert any(
        path.parts[path.parts.index("installer")] == "installer"
        for path, _, _, _ in borrowed
        if "installer" in path.parts
    ), "the setup program borrows nothing from the application any more"


def test_every_borrowed_name_exists_where_it_is_taken_from() -> None:
    """A rename on one side must not leave the other importing a ghost."""
    missing = []
    for path, line, module, name in _borrowed():
        source = _module_file(module)
        if source is None:
            # A module this scan cannot resolve to a file (a namespace package)
            # is not evidence of a broken import, so it is left alone.
            continue
        if name in _defined_names(source):
            continue
        # `from package import submodule` imports a FILE, not a name the
        # package's __init__ defines. That is the commonest shape here.
        if _module_file(f"{module}.{name}") is not None:
            continue
        missing.append(
            f"{path.relative_to(_ROOT)}:{line} imports {name!r} from "
            f"{module}, which does not define it"
        )
    assert not missing, "\n".join(missing)
