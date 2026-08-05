"""The bundled payload, its manifest and the guard on where it may be written.

The payload anchor is redirected by the autouse fixture in conftest, so every
archive here is a small stand-in and the real fifty-megabyte bundle is never
opened. British spelling is used in comments.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from installer.constants import APP_EXE_NAME, APP_INTERNAL_DIR_NAME
from installer.ops.errors import InstallerOperationError, UnsafePayloadEntryError
from installer.ops.payload import (
    ManifestEntry,
    extract_archive,
    iter_manifest_entries,
    load_manifest,
    manifest_json_path,
    payload_zip_path,
    safe_destination,
)
from installer.ops.progress import EXTRACT_END_PCT, EXTRACT_MESSAGE, EXTRACT_START_PCT
from tests.installer.conftest import (
    BUNDLE_NESTED_PATH,
    MANIFEST_JSON_NAME,
    PAYLOAD_ZIP_NAME,
    write_bundle,
)
from tests.installer.fakes import RecordingProgress

_ESCAPE_NAME = "../escaped.txt"
_ABSOLUTE_NAME = "C:/Windows/escaped.txt"
_VERSION = "4.0.0"


class TestLocatingThePayload:
    def test_the_archive_is_found_through_the_resource_anchor(
        self, staged_payload: Path
    ) -> None:
        assert payload_zip_path() == staged_payload / PAYLOAD_ZIP_NAME

    def test_the_manifest_is_found_beside_it(self, staged_payload: Path) -> None:
        assert manifest_json_path() == staged_payload / MANIFEST_JSON_NAME


class TestManifest:
    def _write(self, staged_payload: Path, data: dict) -> None:
        (staged_payload / MANIFEST_JSON_NAME).write_text(
            json.dumps(data), encoding="utf-8"
        )

    def test_it_reads_the_version_and_every_entry(self, staged_payload: Path) -> None:
        self._write(
            staged_payload,
            {
                "installer_version": _VERSION,
                "entries": [{"path": APP_EXE_NAME, "size": 10, "sha256": "abc"}],
            },
        )

        manifest = load_manifest()

        assert manifest.installer_version == _VERSION
        assert tuple(iter_manifest_entries(manifest)) == (
            ManifestEntry(path=APP_EXE_NAME, size=10, sha256="abc"),
        )

    def test_a_manifest_with_no_entries_reads_as_empty(
        self, staged_payload: Path
    ) -> None:
        self._write(staged_payload, {})

        manifest = load_manifest()

        assert manifest.installer_version == ""
        assert manifest.entries == ()


class TestSafeDestination:
    def test_an_ordinary_entry_lands_inside_the_target(self, tmp_path: Path) -> None:
        assert safe_destination(tmp_path, "a/b.txt") == (tmp_path / "a" / "b.txt")

    def test_the_target_itself_is_allowed(self, tmp_path: Path) -> None:
        assert safe_destination(tmp_path, ".") == tmp_path.resolve()

    @pytest.mark.parametrize("name", [_ESCAPE_NAME, _ABSOLUTE_NAME])
    def test_an_entry_that_escapes_the_target_is_refused(
        self, tmp_path: Path, name: str
    ) -> None:
        """First-party payload or not, a write outside the target never happens."""
        target = tmp_path / "install"
        target.mkdir()

        with pytest.raises(UnsafePayloadEntryError):
            safe_destination(target, name)


class TestExtractArchive:
    def test_it_writes_every_member_under_the_target(self, tmp_path: Path) -> None:
        target = tmp_path / "staging"

        extract_archive(payload_zip_path(), target)

        assert (target / APP_EXE_NAME).is_file()
        assert (target / BUNDLE_NESTED_PATH).is_file()

    def test_it_creates_the_directories_the_archive_records(
        self, tmp_path: Path
    ) -> None:
        archive = tmp_path / "with-dirs.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr(f"{APP_INTERNAL_DIR_NAME}/", b"")
        target = tmp_path / "staging"

        extract_archive(archive, target)

        assert (target / APP_INTERNAL_DIR_NAME).is_dir()

    def test_it_reports_progress_across_the_extraction_span(
        self, tmp_path: Path
    ) -> None:
        progress = RecordingProgress()

        extract_archive(payload_zip_path(), tmp_path / "staging", progress=progress)

        assert progress.percentages[0] == EXTRACT_START_PCT
        assert progress.percentages[-1] == EXTRACT_END_PCT
        assert progress.messages[0] == EXTRACT_MESSAGE

    def test_an_empty_archive_still_completes_its_phase(self, tmp_path: Path) -> None:
        """Zero bytes to write must not divide by zero when scaling the bar."""
        archive = tmp_path / "empty.zip"
        with zipfile.ZipFile(archive, "w"):
            pass
        progress = RecordingProgress()

        extract_archive(archive, tmp_path / "staging", progress=progress)

        assert progress.percentages == [EXTRACT_START_PCT]

    def test_an_entry_that_escapes_the_target_stops_the_extraction(
        self, tmp_path: Path
    ) -> None:
        archive = write_bundle(tmp_path / "hostile.zip", extra={_ESCAPE_NAME: b"no"})
        target = tmp_path / "staging"

        with pytest.raises(UnsafePayloadEntryError):
            extract_archive(archive, target)

        assert not (tmp_path / "escaped.txt").exists()

    def test_a_cancel_is_honoured_between_members(self, tmp_path: Path) -> None:
        def _cancel() -> None:
            raise InstallerOperationError("Cancelled")

        with pytest.raises(InstallerOperationError):
            extract_archive(
                payload_zip_path(), tmp_path / "staging", cancel_check=_cancel
            )

    def test_a_missing_archive_is_reported(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            extract_archive(tmp_path / "absent.zip", tmp_path / "staging")
