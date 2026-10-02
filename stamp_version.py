"""Stamp the canonical version into static files that cannot read it at runtime.

The VERSION file at the repo root is the single source of truth. The runtime
(clear_budget.version) and packaging (pyproject.toml dynamic version, the build
scripts) all read it directly. Static assets under docs/ are served as-is by
GitHub Pages and cannot, so this script rewrites the version into them from
VERSION instead.

Two things are stamped:

* delimited tokens ``<!--VERSION-->x.y.z<!--/VERSION-->`` in the docs HTML and
  markdown, for visible version text;
* the JSON-LD ``"softwareVersion": "x.y.z"`` field in docs HTML, where an HTML
  comment token would corrupt the embedded JSON.

The docs tree is the ONLY target. Root markdown (README, ARCHITECTURE,
TECH_DEBT, DEVELOPMENT-README) carries no version data at all: it is read
alongside the source, where VERSION is the answer, so a stamped copy in prose
is one more thing that can disagree with it. The published site is the one
place that cannot read VERSION at render time, which is the whole reason this
script exists.

It also versions the site's own asset links. GitHub Pages lets a browser keep
a stylesheet for ten minutes, so a fresh page can arrive beside its stale CSS
and render broken. Every local ``href="x.css"`` or ``src="x.js"`` in docs HTML
therefore carries ``?v=<hash>`` of the file's content, taken with CRLF folded
to LF so a Windows checkout and the LF blob GitHub serves give the same hash.

It is idempotent (stamping an already-current file changes nothing) and prints
the files it touched. buildexe.py and buildinstaller.py call main() so a release
can never ship static docs whose version disagrees with VERSION.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

VERSION_FILENAME = "VERSION"
FALLBACK_VERSION = "0.0.0-dev"
DOCS_DIRNAME = "docs"
ASSET_HASH_LENGTH = 10

_TOKEN_PATTERN = re.compile(r"(<!--VERSION-->)(.*?)(<!--/VERSION-->)", re.DOTALL)
_SOFTWARE_VERSION_PATTERN = re.compile(r'("softwareVersion"\s*:\s*")([^"]*)(")')
# A stylesheet or script reference; any query it already has is replaced.
_ASSET_LINK_PATTERN = re.compile(
    r"""(?<![\w-])((?:href|src)=)(["'])"""
    r"""([^"'?#]+\.(?:css|js))(?:\?[^"'#]*)?(#[^"']*)?\2"""
)
# Only relative paths are local files: a scheme, `//` or a leading `/` is not.
_NOT_RELATIVE_PATTERN = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*:|/)")


def read_version(root: Path) -> str:
    """Return the canonical version from the VERSION file; else a dev sentinel."""
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
    """Collect the static files that carry a stamped version.

    Scoped to the docs tree deliberately. Root markdown is never stamped.
    """
    docs_dir = root / DOCS_DIRNAME
    if not docs_dir.is_dir():
        return []
    return [*docs_dir.rglob("*.html"), *docs_dir.rglob("*.md")]


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


def _asset_hash(path: Path) -> str:
    """Return the content hash of one asset, with CRLF folded to LF first."""
    if not path.is_file():
        raise FileNotFoundError(f"a docs page links to a missing asset: {path}")
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:ASSET_HASH_LENGTH]


def _link_assets(text: str, page_dir: Path) -> str:
    """Return ``text`` with every local asset link carrying its content hash."""

    def _link(match: re.Match[str]) -> str:
        attribute, quote, target, fragment = match.groups()
        if _NOT_RELATIVE_PATTERN.match(target):
            return match.group(0)
        digest = _asset_hash(page_dir / target)
        return f"{attribute}{quote}{target}?v={digest}{fragment or ''}{quote}"

    return _ASSET_LINK_PATTERN.sub(_link, text)


def version_assets(root: Path) -> list[Path]:
    """Hash every local asset link in the docs HTML; return the pages changed.

    Pages are read and written with newline translation off, so each keeps the
    line endings it already had.
    """
    touched: list[Path] = []
    for path in _target_files(root):
        if path.suffix.lower() != ".html":
            continue
        with path.open("r", encoding="utf-8", newline="") as handle:
            original = handle.read()
        linked = _link_assets(original, path.parent)
        if linked != original:
            with path.open("w", encoding="utf-8", newline="") as handle:
                handle.write(linked)
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
    linked = version_assets(root)
    if linked:
        print(f"Versioned asset links in {len(linked)} file(s):")
        for path in linked:
            print(f"  {path.relative_to(root)}")
    else:
        print("Asset links already current in all docs pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
