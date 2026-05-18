"""Access embedded payload and manifest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from installer.shared.resource_path import resource_path


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
    return resource_path("installer/payload/payload.zip")


def manifest_json_path() -> Path:
    return resource_path("installer/payload/manifest.json")


def load_manifest() -> PayloadManifest:
    data = json.loads(manifest_json_path().read_text(encoding="utf-8"))
    entries = tuple(ManifestEntry(**e) for e in data.get("entries", []))
    return PayloadManifest(
        installer_version=str(data.get("installer_version", "")), entries=entries
    )


def iter_manifest_entries(manifest: PayloadManifest) -> Iterable[ManifestEntry]:
    return manifest.entries
