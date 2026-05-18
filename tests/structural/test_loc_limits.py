"""Structural tests for LOC (lines of code) limits.

Verifies that no Python file in the project exceeds 400 lines of code.
This enforces code readability and maintainability constraints.
"""

from pathlib import Path


class TestLOCLimits:
    """Test that files don't exceed LOC limits."""

    def test_all_python_files_under_400_loc(self):
        """No Python file should exceed 400 lines of code."""
        project_root = Path(__file__).parent.parent.parent
        violations = []

        # Scan all Python files except __pycache__, venv, and build artifacts
        for py_file in project_root.rglob("*.py"):
            if any(
                part in py_file.parts
                for part in ["__pycache__", "venv", ".venv", "build", "dist", "dist-installer", "dist-pyinstaller", ".egg"]
            ):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    loc = len(lines)
            except (UnicodeDecodeError, IOError):
                # Skip files with encoding issues
                continue

            if loc > 400:
                rel_path = py_file.relative_to(project_root)
                violations.append(f"{rel_path}: {loc} lines (limit: 400)")

        assert not violations, (
            f"Files exceed 400 LOC limit:\n" + "\n".join(violations)
        )

    def test_test_files_under_400_loc(self):
        """Test files also must not exceed 400 lines of code."""
        project_root = Path(__file__).parent.parent
        test_dir = project_root

        violations = []

        for py_file in test_dir.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    loc = len(lines)
            except (UnicodeDecodeError, IOError):
                continue

            if loc > 400:
                rel_path = py_file.relative_to(project_root)
                violations.append(f"{rel_path}: {loc} lines (limit: 400)")

        assert not violations, (
            f"Test files exceed 400 LOC limit:\n" + "\n".join(violations)
        )
