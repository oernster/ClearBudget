"""The application bundle the setup program carries: putting it on disk.

Extraction is member by member rather than a single ``extractall``: it lets the
operation report real progress across the longest phase of an install; it also
lets every entry be checked before it is written.

The payload is produced by this project's own ``build_payload.py``, so a member
that escapes its destination is not the expected case. Extraction runs with the
user's full privileges, though, so the guarantee is enforced here rather than
assumed. British spelling is used in comments.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from installer.constants import MANIFEST_JSON_RESOURCE, PAYLOAD_ZIP_RESOURCE
from installer.ops.errors import UnsafePayloadEntryError
from installer.ops.progress import (
    EXTRACT_END_PCT,
    EXTRACT_MESSAGE,
    EXTRACT_START_PCT,
    ProgressCallback,
    report,
    scaled,
)
from installer.shared.resource_path import resource_path

_ENTRIES_KEY = "entries"
_INSTALLER_VERSION_KEY = "installer_version"

# Consulted between members so a cancel during the longest phase is honoured
# promptly rather than at the end of it. It raises rather than returning a flag,
# because the operations already unwind through a typed error.
CancelCheck = Callable[[], None]


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class PayloadManifest:
    installer_version: str
    entries: tuple[ManifestEntry, ...]


def payload_zip_path() -> Path:
    return resource_path(PAYLOAD_ZIP_RESOURCE)


def manifest_json_path() -> Path:
    return resource_path(MANIFEST_JSON_RESOURCE)


def load_manifest() -> PayloadManifest:
    data = json.loads(manifest_json_path().read_text(encoding="utf-8"))
    entries = tuple(ManifestEntry(**e) for e in data.get(_ENTRIES_KEY, []))
    return PayloadManifest(
        installer_version=str(data.get(_INSTALLER_VERSION_KEY, "")), entries=entries
    )


def iter_manifest_entries(manifest: PayloadManifest) -> Iterable[ManifestEntry]:
    return manifest.entries


def safe_destination(root: Path, name: str) -> Path:
    """Return the path an entry writes to, refusing one that escapes ``root``.

    This is the guard behind every write the installer makes from payload data,
    whether the name comes from the archive's own member list or from the
    repair manifest. Both are first-party, so this enforces a guarantee rather
    than fixing an exploit; enforcing it is what keeps the guarantee true.
    """
    destination = (root / name).resolve()
    anchor = root.resolve()
    if destination != anchor and anchor not in destination.parents:
        raise UnsafePayloadEntryError(
            f"Payload entry {name!r} would be written outside {anchor}."
        )
    return destination


def extract_archive(
    archive: Path,
    target: Path,
    *,
    progress: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> None:
    """Extract ``archive`` into ``target``, reporting progress as it goes."""
    target.mkdir(parents=True, exist_ok=True)
    report(progress, EXTRACT_START_PCT, EXTRACT_MESSAGE)

    with zipfile.ZipFile(archive, "r") as bundle:
        members = bundle.infolist()
        total = sum(member.file_size for member in members)
        written = 0
        for member in members:
            if cancel_check is not None:
                cancel_check()
            destination = safe_destination(target, member.filename)
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, destination.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            written += member.file_size
            report(
                progress,
                scaled(written, total, EXTRACT_START_PCT, EXTRACT_END_PCT),
                EXTRACT_MESSAGE,
            )
