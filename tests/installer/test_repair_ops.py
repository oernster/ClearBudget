"""Repair: verifying the manifest and restoring what no longer matches.

Repair reads its own registration, so each test installs first and then damages
the result, which is the situation a repair actually meets. British spelling is
used in comments.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from installer.constants import APP_EXE_NAME, InstallerIdentity
from installer.ops.errors import (
    AppRunningError,
    InstallerOperationError,
    UnsafePayloadEntryError,
)
from installer.ops.install_ops import InstallOptions, install_new
from installer.ops.payload import ManifestEntry
from installer.ops.progress import (
    COMPLETE_PCT,
    REPAIR_CLEANUP_PCT,
    RESTORE_REGISTRY_PCT,
    RESTORE_SHORTCUTS_PCT,
    VERIFY_END_PCT,
    VERIFY_START_PCT,
)
from installer.ops.repair_ops import (
    NOT_INSTALLED_MESSAGE,
    WINDOWS_ONLY_MESSAGE,
    RepairOptions,
    needs_restoring,
    repair,
)
from installer.ops.shortcuts import get_shortcut_paths
from installer.state.registry import read_uninstall_entry
from tests.installer.conftest import (
    BUNDLE_EXE_BYTES,
    BUNDLE_NESTED_BYTES,
    BUNDLE_NESTED_PATH,
    MANIFEST_JSON_NAME,
)
from tests.installer.fakes import (
    CancelledEvent,
    FakeProcessController,
    RecordingProgress,
)

_PID = 555
_DAMAGED = b"damaged"
_ESCAPING_PATH = "../escaped.txt"


def _entry_for(path: str, data: bytes) -> dict[str, object]:
    return {
        "path": path,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


@pytest.fixture()
def manifest(staged_payload: Path) -> Path:
    """Write a manifest matching the stand-in bundle."""
    path = staged_payload / MANIFEST_JSON_NAME
    path.write_text(
        json.dumps(
            {
                "installer_version": "4.0.0",
                "entries": [
                    _entry_for(APP_EXE_NAME, BUNDLE_EXE_BYTES),
                    _entry_for(BUNDLE_NESTED_PATH, BUNDLE_NESTED_BYTES),
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def installed(
    scratch_identity: InstallerIdentity, tmp_path: Path, manifest: Path
) -> Path:
    """Install once, so a repair has something to repair."""
    target = tmp_path / "programs" / "ClearBudget"
    install_new(
        scratch_identity,
        InstallOptions(
            target_dir=target,
            create_desktop_shortcut=False,
            create_start_menu_shortcut=False,
        ),
        controller=FakeProcessController(),
    )
    return target


def _options(*, desktop: bool = False, start_menu: bool = False) -> RepairOptions:
    return RepairOptions(
        restore_desktop_shortcut=desktop, restore_start_menu_shortcut=start_menu
    )


class TestNeedsRestoring:
    def test_a_missing_file_needs_restoring(self, tmp_path: Path) -> None:
        entry = ManifestEntry(**_entry_for(APP_EXE_NAME, BUNDLE_EXE_BYTES))

        assert needs_restoring(tmp_path / APP_EXE_NAME, entry) is True

    def test_a_matching_file_is_left_alone(self, tmp_path: Path) -> None:
        path = tmp_path / APP_EXE_NAME
        path.write_bytes(BUNDLE_EXE_BYTES)
        entry = ManifestEntry(**_entry_for(APP_EXE_NAME, BUNDLE_EXE_BYTES))

        assert needs_restoring(path, entry) is False

    def test_a_file_of_the_wrong_size_needs_restoring(self, tmp_path: Path) -> None:
        path = tmp_path / APP_EXE_NAME
        path.write_bytes(BUNDLE_EXE_BYTES + b"extra")
        entry = ManifestEntry(**_entry_for(APP_EXE_NAME, BUNDLE_EXE_BYTES))

        assert needs_restoring(path, entry) is True

    def test_a_file_of_the_right_size_but_wrong_content_needs_restoring(
        self, tmp_path: Path
    ) -> None:
        """The size check alone would pass this, which is why the hash is read."""
        path = tmp_path / APP_EXE_NAME
        path.write_bytes(b"x" * len(BUNDLE_EXE_BYTES))
        entry = ManifestEntry(**_entry_for(APP_EXE_NAME, BUNDLE_EXE_BYTES))

        assert needs_restoring(path, entry) is True

    def test_a_file_that_cannot_be_read_needs_restoring(self, tmp_path: Path) -> None:
        """A directory where a file belongs: it reports a size but cannot be
        opened, so the hash read fails and restoring it is the safe answer."""
        path = tmp_path / APP_EXE_NAME
        path.mkdir()
        entry = ManifestEntry(
            path=APP_EXE_NAME, size=path.stat().st_size, sha256="whatever"
        )

        assert needs_restoring(path, entry) is True


class TestRepair:
    def test_it_restores_a_deleted_file(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        (installed / APP_EXE_NAME).unlink()

        repair(scratch_identity, _options(), controller=FakeProcessController())

        assert (installed / APP_EXE_NAME).read_bytes() == BUNDLE_EXE_BYTES

    def test_it_restores_an_altered_file(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        (installed / BUNDLE_NESTED_PATH).write_bytes(_DAMAGED)

        repair(scratch_identity, _options(), controller=FakeProcessController())

        assert (installed / BUNDLE_NESTED_PATH).read_bytes() == BUNDLE_NESTED_BYTES

    def test_it_reports_a_percentage_for_every_phase(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        """The bar used to sit at zero and jump to complete; now it moves."""
        progress = RecordingProgress()

        repair(
            scratch_identity,
            _options(),
            progress=progress,
            controller=FakeProcessController(),
        )

        assert progress.percentages[0] >= VERIFY_START_PCT
        assert VERIFY_END_PCT in progress.percentages
        assert RESTORE_SHORTCUTS_PCT in progress.percentages
        assert RESTORE_REGISTRY_PCT in progress.percentages
        assert REPAIR_CLEANUP_PCT in progress.percentages
        assert progress.percentages[-1] == COMPLETE_PCT

    def test_the_verification_percentages_climb_across_the_manifest(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        progress = RecordingProgress()

        repair(
            scratch_identity,
            _options(),
            progress=progress,
            controller=FakeProcessController(),
        )

        assert progress.percentages == sorted(progress.percentages)
        assert len(set(progress.percentages)) > 1

    def test_it_names_the_file_it_is_working_on(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        progress = RecordingProgress()

        repair(
            scratch_identity,
            _options(),
            progress=progress,
            controller=FakeProcessController(),
        )

        assert any(APP_EXE_NAME in message for message in progress.messages)

    def test_it_restores_missing_shortcuts_when_asked(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        repair(
            scratch_identity,
            _options(desktop=True, start_menu=True),
            controller=FakeProcessController(),
        )

        paths = get_shortcut_paths(scratch_identity)
        assert paths.desktop_lnk.is_file()
        assert paths.start_menu_lnk.is_file()

    def test_an_existing_shortcut_is_left_as_it_is(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        paths = get_shortcut_paths(scratch_identity)
        paths.desktop_lnk.parent.mkdir(parents=True, exist_ok=True)
        paths.desktop_lnk.write_bytes(b"existing")

        repair(
            scratch_identity, _options(desktop=True), controller=FakeProcessController()
        )

        assert paths.desktop_lnk.read_bytes() == b"existing"

    def test_it_restores_the_registry_metadata(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        repair(
            scratch_identity, _options(desktop=True), controller=FakeProcessController()
        )

        entry = read_uninstall_entry(scratch_identity.uninstall_key)
        assert entry is not None
        assert entry.shortcut_desktop is True
        assert entry.install_location == installed

    def test_it_refuses_when_nothing_is_installed(
        self, scratch_identity: InstallerIdentity, manifest: Path
    ) -> None:
        with pytest.raises(InstallerOperationError, match=NOT_INSTALLED_MESSAGE):
            repair(scratch_identity, _options(), controller=FakeProcessController())

    def test_it_refuses_when_the_recorded_location_has_gone(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        import shutil

        shutil.rmtree(installed)

        with pytest.raises(InstallerOperationError, match=NOT_INSTALLED_MESSAGE):
            repair(scratch_identity, _options(), controller=FakeProcessController())

    def test_it_refuses_while_the_application_is_running(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        exe = installed / APP_EXE_NAME

        with pytest.raises(AppRunningError):
            repair(
                scratch_identity,
                _options(),
                controller=FakeProcessController(exe, [_PID]),
            )

    def test_a_cancel_stops_the_walk(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        with pytest.raises(InstallerOperationError, match="Cancelled"):
            repair(
                scratch_identity,
                _options(),
                cancel_event=CancelledEvent(),
                controller=FakeProcessController(),
            )

    def test_a_manifest_path_that_escapes_the_install_is_refused(
        self,
        scratch_identity: InstallerIdentity,
        installed: Path,
        staged_payload: Path,
    ) -> None:
        """The manifest is first-party, so this enforces a guarantee, not a fix."""
        (staged_payload / MANIFEST_JSON_NAME).write_text(
            json.dumps({"entries": [_entry_for(_ESCAPING_PATH, b"no")]}),
            encoding="utf-8",
        )

        with pytest.raises(UnsafePayloadEntryError):
            repair(scratch_identity, _options(), controller=FakeProcessController())

        assert not (installed.parent / "escaped.txt").exists()

    def test_it_is_windows_only(
        self,
        scratch_identity: InstallerIdentity,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(os, "name", "posix")

        with pytest.raises(InstallerOperationError, match=WINDOWS_ONLY_MESSAGE):
            repair(scratch_identity, _options())
