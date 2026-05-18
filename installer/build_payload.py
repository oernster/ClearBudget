"""Build the installer payload zip + manifest.

Input:
    dist-pyinstaller/ClearBudget/  (PyInstaller onedir bundle)

Output:
    installer/payload/payload.zip
    installer/payload/manifest.json

The payload is deterministic:

- files are added in sorted order
- zip timestamps are normalized
"""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from clear_budget.version import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_BUNDLE_DIR = PROJECT_ROOT / "dist-pyinstaller" / "ClearBudget"
PAYLOAD_DIR = PROJECT_ROOT / "installer" / "payload"
PAYLOAD_ZIP = PAYLOAD_DIR / "payload.zip"
MANIFEST_JSON = PAYLOAD_DIR / "manifest.json"


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    path: str
    size: int
    sha256: str


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(root)
            if any(part in {"__pycache__"} for part in rel.parts):
                continue
            files.append(p)
    return sorted(files, key=lambda x: str(x.relative_to(root)).replace("\\", "/"))


def build_payload() -> None:
    if os.name != "nt":
        raise SystemExit("Payload build is intended for Windows builds")

    if not SOURCE_BUNDLE_DIR.exists():
        raise SystemExit(f"Source bundle not found: {SOURCE_BUNDLE_DIR}")

    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)

    entries: list[ManifestEntry] = []

    fixed_dt = (1980, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(PAYLOAD_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in _iter_files(SOURCE_BUNDLE_DIR):
            rel = file_path.relative_to(SOURCE_BUNDLE_DIR)
            rel_posix = str(rel).replace("\\", "/")
            size = file_path.stat().st_size
            sha = _sha256_file(file_path)
            entries.append(ManifestEntry(path=rel_posix, size=size, sha256=sha))

            zi = zipfile.ZipInfo(filename=rel_posix, date_time=fixed_dt)
            zi.compress_type = zipfile.ZIP_DEFLATED

            with file_path.open("rb") as src:
                data = src.read()
            zf.writestr(zi, data)

    manifest = {
        "installer_version": __version__,
        "bundle_root": "ClearBudget",
        "entries": [asdict(e) for e in entries],
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build_payload()
