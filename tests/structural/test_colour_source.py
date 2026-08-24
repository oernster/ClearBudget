"""One home for colour values, enforced rather than remembered.

`clear_budget/shared/palette.py` is the single source of truth for every colour
the app paints. This scan fails the build if a hex literal appears anywhere
else, because the alternative is what the tree looked like before: the focus
ring and the chart's positive bars sharing one value with nobody able to see
it, plus the report layer mirroring thirty-one values by hand until they drifted.

Prose is exempt. A docstring or comment may quote a hex when it is recording a
decision (why a blue was rejected, what a measurement was), because that is
history rather than a value anything paints from. Only string CONSTANTS count.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_PACKAGES = ("clear_budget", "installer")
_SOURCE_OF_TRUTH = _REPO / "clear_budget" / "shared" / "palette.py"

# A colour literal: # followed by exactly 3, 6 or 8 hex digits. The lookbehind
# keeps HTML numeric entities out (`&#128260;` is an emoji, not a colour) and
# the lookahead stops a longer digit run matching its own prefix.
_HEX = re.compile(
    r"(?<!&)#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])"
)


def _python_files() -> list[Path]:
    files: list[Path] = []
    for package in _PACKAGES:
        for path in (_REPO / package).rglob("*.py"):
            if "__pycache__" in path.parts or path == _SOURCE_OF_TRUTH:
                continue
            files.append(path)
    return files


def _docstrings(tree: ast.AST) -> set[str]:
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, holders):
            text = ast.get_docstring(node, clean=False)
            if text:
                found.add(text)
    return found


def _literals_in(path: Path) -> list[tuple[int, str]]:
    """Every colour literal held in a string CONSTANT of `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    prose = _docstrings(tree)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if node.value in prose:
            continue
        hits.extend((node.lineno, found) for found in _HEX.findall(node.value))
    return hits


def test_no_colour_literal_lives_outside_the_palette() -> None:
    """Every colour value comes from `shared.palette`; nowhere else."""
    offenders = []
    for path in _python_files():
        for line, colour in _literals_in(path):
            offenders.append(f"{path.relative_to(_REPO)}:{line}: {colour}")

    assert not offenders, (
        "colour literals must live in clear_budget/shared/palette.py and be "
        "referenced by name from everywhere else:\n  " + "\n  ".join(offenders)
    )


def test_the_palette_actually_holds_colours() -> None:
    """Guard the guard: an empty or renamed palette must not read as clean."""
    names = [
        node.targets[0].id
        for node in ast.parse(_SOURCE_OF_TRUTH.read_text(encoding="utf-8")).body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
        and _HEX.fullmatch(node.value.value)
    ]
    assert len(names) > 50, f"the palette holds only {len(names)} colours"
    assert len(names) == len(set(names)), "a colour name is defined twice"
