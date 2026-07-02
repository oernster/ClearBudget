"""Stamp the canonical version into static files that cannot read it at runtime.

The VERSION file at the repo root is the single source of truth. The runtime
(clear_budget.version) and packaging (pyproject.toml dynamic version, the build
scripts) all read it directly. Static assets under docs/ are served as-is by
GitHub Pages and cannot, so this script rewrites the version into them from
VERSION instead.

Two things are stamped:

* delimited tokens ``<!--VERSION-->x.y.z<!--/VERSION-->`` in root markdown and
  any docs HTML or markdown, for visible version text;
* the JSON-LD ``"softwareVersion": "x.y.z"`` field in docs HTML, where an HTML
  comment token would corrupt the embedded JSON.

It is idempotent (stamping an already-current file changes nothing) and prints
the files it touched. buildexe.py and buildinstaller.py call main() so a release
can never ship static docs whose version disagrees with VERSION.
"""

from __future__ import annotations

import re
from pathlib import Path

VERSION_FILENAME = "VERSION"
FALLBACK_VERSION = "0.0.0-dev"
DOCS_DIRNAME = "docs"

_TOKEN_PATTERN = re.compile(r"(<!--VERSION-->)(.*?)(<!--/VERSION-->)", re.DOTALL)
_SOFTWARE_VERSION_PATTERN = re.compile(r'("softwareVersion"\s*:\s*")([^"]*)(")')


def read_version(root: Path) -> str:
    """Return the canonical version from the VERSION file, or a dev sentinel."""
    version_file = root / VERSION_FILENAME
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return FALLBACK_VERSION


def _stamp_text(text: str, version: str, *, is_html: bool) -> str:
    """Return ``text`` with every version token and JSON-LD field set to version."""
    stamped = _TOKEN_PATTERN.sub(lambda m: f"{m.group(1)}{version}{m.group(3)}", text)
    if is_html:
        stamped = _SOFTWARE_VERSION_PATTERN.sub(
            lambda m: f"{m.group(1)}{version}{m.group(3)}", stamped
        )
    return stamped


def _target_files(root: Path) -> list[Path]:
    """Collect the static files that carry a stamped version."""
    files = list(root.glob("*.md"))
    docs_dir = root / DOCS_DIRNAME
    if docs_dir.is_dir():
        files.extend(docs_dir.rglob("*.html"))
        files.extend(docs_dir.rglob("*.md"))
    return files


def stamp(root: Path, version: str) -> list[Path]:
    """Stamp ``version`` into every target file; return the ones that changed."""
    touched: list[Path] = []
    for path in _target_files(root):
        original = path.read_text(encoding="utf-8")
        stamped = _stamp_text(original, version, is_html=path.suffix.lower() == ".html")
        if stamped != original:
            path.write_text(stamped, encoding="utf-8")
            touched.append(path)
    return touched


def main() -> int:
    """Stamp the repo's static files from VERSION and report what changed."""
    root = Path(__file__).resolve().parent
    version = read_version(root)
    touched = stamp(root, version)
    if touched:
        print(f"Stamped version {version} into {len(touched)} file(s):")
        for path in touched:
            print(f"  {path.relative_to(root)}")
    else:
        print(f"Version {version} already current in all static files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
