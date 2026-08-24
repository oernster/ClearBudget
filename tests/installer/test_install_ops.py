"""Install, upgrade and reinstall, end to end against scratch state.

The payload anchor, the profile directories, the platformdirs lookups and the
registry key are all redirected, so a full install runs here without touching a
real installation. British spelling is used in comments.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from installer.constants import (
    APP_EXE_NAME,
    APP_INTERNAL_DIR_NAME,
    STAGING_PREFIX,
    InstallerIdentity,
)
from installer.ops.errors import AppRunningError, InstallerOperationError
from installer.ops.install_ops import (
    InstallOptions,
    apply_shortcuts,
    guard_not_running,
    install_new,
    upgrade_or_reinstall,
)
from installer.ops.progress import (
    CLEANUP_PCT,
    COMPLETE_PCT,
    REGISTER_PCT,
    SHORTCUTS_MESSAGE,
    SWAP_PCT,
    UPDATE_SHORTCUTS_MESSAGE,
)
from installer.ops.shortcuts import get_shortcut_paths
from installer.state.registry import read_uninstall_entry
from tests.installer.conftest import BUNDLE_NESTED_PATH, PAYLOAD_ZIP_NAME, write_bundle
from tests.installer.fakes import (
    CancelledEvent,
    CountdownEvent,
    FakeProcessController,
    RecordingProgress,
)

_PID = 999


def _options(target: Path, *, desktop: bool = False, start_menu: bool = False):
    return InstallOptions(
        target_dir=target,
        create_desktop_shortcut=desktop,
        create_start_menu_shortcut=start_menu,
    )


@pytest.fixture()
def target(tmp_path: Path) -> Path:
    """Return the directory an install writes into."""
    return tmp_path / "programs" / "ClearBudget"


class TestGuardNotRunning:
    def test_an_empty_directory_is_never_running(self, tmp_path: Path) -> None:
        guard_not_running(tmp_path, FakeProcessController())

    def test_an_idle_installation_passes(self, tmp_path: Path) -> None:
        (tmp_path / APP_EXE_NAME).write_bytes(b"exe")

        guard_not_running(tmp_path, FakeProcessController())

    def test_a_running_installation_is_refused(self, tmp_path: Path) -> None:
        exe = tmp_path / APP_EXE_NAME
        exe.write_bytes(b"exe")

        with pytest.raises(AppRunningError):
            guard_not_running(tmp_path, FakeProcessController(exe, [_PID]))


class TestInstallNew:
    def test_it_deploys_the_bundle_and_registers_the_installation(
        self, scratch_identity: InstallerIdentity, target: Path
    ) -> None:
        install_new(
            scratch_identity, _options(target), controller=FakeProcessController()
        )

        assert (target / APP_EXE_NAME).is_file()
        assert (target / BUNDLE_NESTED_PATH).is_file()
        entry = read_uninstall_entry(scratch_identity.uninstall_key)
        assert entry is not None
        assert entry.install_location == target

    def test_it_reports_progress_from_start_to_completion(
        self, scratch_identity: InstallerIdentity, target: Path
    ) -> None:
        progress = RecordingProgress()

        install_new(
            scratch_identity,
            _options(target),
            progress=progress,
            controller=FakeProcessController(),
        )

        assert SWAP_PCT in progress.percentages
        assert REGISTER_PCT in progress.percentages
        assert CLEANUP_PCT in progress.percentages
        assert progress.percentages[-1] == COMPLETE_PCT
        assert SHORTCUTS_MESSAGE in progress.messages

    def test_the_reported_percentages_never_go_backwards(
        self, scratch_identity: InstallerIdentity, target: Path
    ) -> None:
        progress = RecordingProgress()

        install_new(
            scratch_identity,
            _options(target),
            progress=progress,
            controller=FakeProcessController(),
        )

        assert progress.percentages == sorted(progress.percentages)

    def test_it_refuses_to_install_over_a_running_application(
        self, scratch_identity: InstallerIdentity, target: Path
    ) -> None:
        """A fresh install is guarded too: the directory may already hold a copy."""
        target.mkdir(parents=True)
        exe = target / APP_EXE_NAME
        exe.write_bytes(b"exe")

        with pytest.raises(AppRunningError):
            install_new(
                scratch_identity,
                _options(target),
                controller=FakeProcessController(exe, [_PID]),
            )

        assert read_uninstall_entry(scratch_identity.uninstall_key) is None

    def test_a_truncated_payload_is_reported_rather_than_deployed(
        self,
        scratch_identity: InstallerIdentity,
        staged_payload: Path,
        target: Path,
    ) -> None:
        (staged_payload / PAYLOAD_ZIP_NAME).unlink()
        write_bundle(staged_payload / PAYLOAD_ZIP_NAME)
        _strip_from_bundle(staged_payload / PAYLOAD_ZIP_NAME, APP_INTERNAL_DIR_NAME)

        with pytest.raises(InstallerOperationError, match=APP_INTERNAL_DIR_NAME):
            install_new(
                scratch_identity, _options(target), controller=FakeProcessController()
            )

    def test_a_cancel_stops_the_install_and_clears_the_staging_directory(
        self, scratch_identity: InstallerIdentity, target: Path
    ) -> None:
        with pytest.raises(InstallerOperationError, match="Cancelled"):
            install_new(
                scratch_identity,
                _options(target),
                cancel_event=CancelledEvent(),
                controller=FakeProcessController(),
            )

        assert not target.exists()
        assert _staging_dirs(target.parent) == []

    def test_a_cancel_part_way_through_still_clears_the_staging_directory(
        self, scratch_identity: InstallerIdentity, target: Path
    ) -> None:
        with pytest.raises(InstallerOperationError, match="Cancelled"):
            install_new(
                scratch_identity,
                _options(target),
                cancel_event=CountdownEvent(2),
                controller=FakeProcessController(),
            )

        assert _staging_dirs(target.parent) == []

    def test_it_creates_the_shortcuts_the_user_asked_for(
        self, scratch_identity: InstallerIdentity, target: Path
    ) -> None:
        install_new(
            scratch_identity,
            _options(target, desktop=True, start_menu=True),
            controller=FakeProcessController(),
        )

        paths = get_shortcut_paths(scratch_identity)
        assert paths.desktop_lnk.is_file()
        assert paths.start_menu_lnk.is_file()


class TestUpgradeOrReinstall:
    def test_it_replaces_an_install_in_place(
        self, scratch_identity: InstallerIdentity, target: Path
    ) -> None:
        install_new(
            scratch_identity, _options(target), controller=FakeProcessController()
        )
        (target / APP_EXE_NAME).unlink()

        upgrade_or_reinstall(
            scratch_identity,
            current_install_dir=target,
            opts=_options(target),
            controller=FakeProcessController(),
        )

        assert (target / APP_EXE_NAME).is_file()

    def test_moving_to_a_new_directory_leaves_the_old_one_behind(
        self, scratch_identity: InstallerIdentity, target: Path, tmp_path: Path
    ) -> None:
        install_new(
            scratch_identity, _options(target), controller=FakeProcessController()
        )
        moved = tmp_path / "programs" / "ClearBudget Elsewhere"

        upgrade_or_reinstall(
            scratch_identity,
            current_install_dir=target,
            opts=_options(moved),
            controller=FakeProcessController(),
        )

        assert (moved / APP_EXE_NAME).is_file()
        assert not target.exists()
        entry = read_uninstall_entry(scratch_identity.uninstall_key)
        assert entry is not None
        assert entry.install_location == moved

    def test_it_reports_that_it_is_updating_the_shortcuts(
        self, scratch_identity: InstallerIdentity, target: Path
    ) -> None:
        progress = RecordingProgress()

        upgrade_or_reinstall(
            scratch_identity,
            current_install_dir=target,
            opts=_options(target),
            progress=progress,
            controller=FakeProcessController(),
        )

        assert UPDATE_SHORTCUTS_MESSAGE in progress.messages
        assert progress.percentages[-1] == COMPLETE_PCT

    def test_a_cancel_clears_the_staging_directory_here_too(
        self, scratch_identity: InstallerIdentity, target: Path
    ) -> None:
        with pytest.raises(InstallerOperationError, match="Cancelled"):
            upgrade_or_reinstall(
                scratch_identity,
                current_install_dir=target,
                opts=_options(target),
                cancel_event=CountdownEvent(2),
                controller=FakeProcessController(),
            )

        assert _staging_dirs(target.parent) == []

    def test_it_refuses_while_the_installed_application_is_running(
        self, scratch_identity: InstallerIdentity, target: Path
    ) -> None:
        target.mkdir(parents=True)
        exe = target / APP_EXE_NAME
        exe.write_bytes(b"exe")

        with pytest.raises(AppRunningError):
            upgrade_or_reinstall(
                scratch_identity,
                current_install_dir=target,
                opts=_options(target),
                controller=FakeProcessController(exe, [_PID]),
            )


class TestApplyShortcuts:
    def test_clearing_the_boxes_removes_shortcuts_a_previous_run_made(
        self, scratch_identity: InstallerIdentity, target: Path
    ) -> None:
        install_new(
            scratch_identity,
            _options(target, desktop=True, start_menu=True),
            controller=FakeProcessController(),
        )
        paths = get_shortcut_paths(scratch_identity)

        apply_shortcuts(scratch_identity, target, _options(target))

        assert not paths.desktop_lnk.exists()
        assert not paths.start_menu_lnk.exists()


def _staging_dirs(parent: Path) -> list[Path]:
    """Return any staging directories left beside an install target."""
    if not parent.exists():
        return []
    return [p for p in parent.iterdir() if p.name.startswith(STAGING_PREFIX)]


def _strip_from_bundle(archive: Path, prefix: str) -> None:
    """Rewrite a bundle without the members under ``prefix``."""
    import zipfile

    keep = []
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            if not member.filename.startswith(prefix):
                keep.append((member.filename, bundle.read(member)))
    with zipfile.ZipFile(archive, "w") as bundle:
        for name, data in keep:
            bundle.writestr(name, data)
