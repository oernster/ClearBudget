"""Staging a bundle, swapping it into place and registering the result.

The registry writes all go to the scratch key the identity fixture yields, so
the user's own Apps and features entry is never read or written. British
spelling is used in comments.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from clear_budget.version import APP_AUTHOR, APP_NAME, __version__
from installer.constants import (
    APP_ICO_NAME,
    APP_ICON_PNG_NAMES,
    STAGING_PREFIX,
    InstallerIdentity,
)
from installer.ops.errors import InstallerOperationError
from installer.ops.registration import (
    UNINSTALL_FLAG,
    copy_self_to_install,
    deploy_runtime_icon_assets,
    display_icon_for,
    installed_exe,
    register_uninstall,
)
from installer.ops.staging import check_cancel, staging_dir_for, swap_in_bundle
from installer.state.registry import read_uninstall_entry
from tests.installer.fakes import CancelledEvent, LiveEvent

_PURPOSE = "install"
_STAGED_MARKER = "staged.txt"
_OLD_MARKER = "old.txt"


class TestCheckCancel:
    def test_no_event_at_all_never_cancels(self) -> None:
        check_cancel(None)

    def test_a_live_operation_carries_on(self) -> None:
        check_cancel(LiveEvent())

    def test_a_cancelled_operation_stops(self) -> None:
        with pytest.raises(InstallerOperationError):
            check_cancel(CancelledEvent())


class TestStagingDir:
    def test_it_sits_beside_the_target_so_the_swap_is_a_rename(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "install" / "Clear Budget"

        staging = staging_dir_for(target, _PURPOSE)

        assert staging.parent == target.parent
        assert staging.name.startswith(f"{STAGING_PREFIX}.{_PURPOSE}.")

    def test_two_runs_never_collide(self, tmp_path: Path) -> None:
        target = tmp_path / "install"

        assert staging_dir_for(target, _PURPOSE) != staging_dir_for(target, _PURPOSE)

    def test_a_stale_directory_left_by_an_interrupted_run_is_cleared(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "install"
        target.mkdir()
        fixed = "deadbeef"
        monkeypatch.setattr(
            "installer.ops.staging.uuid.uuid4", lambda: _FixedUuid(fixed)
        )
        stale = staging_dir_for(target, _PURPOSE)
        stale.mkdir(parents=True)
        (stale / "left-over.txt").write_text("stale", encoding="utf-8")

        fresh = staging_dir_for(target, _PURPOSE)

        assert fresh == stale
        assert not fresh.exists()


class _FixedUuid:
    """A uuid4 stand-in with a hex value the test chooses."""

    def __init__(self, hex_value: str) -> None:
        self.hex = hex_value


class TestSwapInBundle:
    def _staged(self, tmp_path: Path) -> Path:
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / _STAGED_MARKER).write_text("new", encoding="utf-8")
        return staging

    def test_a_first_install_moves_the_bundle_into_place(self, tmp_path: Path) -> None:
        target = tmp_path / "install"

        swap_in_bundle(self._staged(tmp_path), target)

        assert (target / _STAGED_MARKER).read_text(encoding="utf-8") == "new"

    def test_an_existing_install_is_replaced_not_merged(self, tmp_path: Path) -> None:
        target = tmp_path / "install"
        target.mkdir()
        (target / _OLD_MARKER).write_text("old", encoding="utf-8")

        swap_in_bundle(self._staged(tmp_path), target)

        assert (target / _STAGED_MARKER).is_file()
        assert not (target / _OLD_MARKER).exists()

    def test_the_previous_install_is_not_left_lying_beside_the_new_one(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "install"
        target.mkdir()

        swap_in_bundle(self._staged(tmp_path), target)

        assert [p.name for p in tmp_path.iterdir() if ".old." in p.name] == []

    def test_a_target_that_cannot_be_moved_aside_is_reported(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "install"
        target.mkdir()
        held = (target / "held.txt").open("w", encoding="utf-8")
        try:
            with pytest.raises(InstallerOperationError):
                swap_in_bundle(self._staged(tmp_path), target)
        finally:
            held.close()

    def test_a_cross_volume_move_falls_back_to_a_copy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """rename cannot cross volumes, so the bundle is copied instead."""
        staging = self._staged(tmp_path)
        target = tmp_path / "install"
        original = Path.rename

        def _refuse(self: Path, *args: object) -> None:
            if self == staging:
                raise OSError("cross-device link")
            return original(self, *args)

        monkeypatch.setattr(Path, "rename", _refuse)

        swap_in_bundle(staging, target)

        assert (target / _STAGED_MARKER).is_file()
        assert not staging.exists()

    def test_a_failed_swap_puts_the_previous_install_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        staging = self._staged(tmp_path)
        target = tmp_path / "install"
        target.mkdir()
        (target / _OLD_MARKER).write_text("old", encoding="utf-8")
        original = Path.rename

        def _fail_the_staged_move(self: Path, *args: object) -> None:
            if self == staging:
                raise OSError("no")
            return original(self, *args)

        monkeypatch.setattr(Path, "rename", _fail_the_staged_move)
        monkeypatch.setattr("installer.ops.staging.shutil.copytree", _raise_copytree)

        with pytest.raises(OSError):
            swap_in_bundle(staging, target)

        assert (target / _OLD_MARKER).read_text(encoding="utf-8") == "old"

    def test_a_failed_first_install_has_no_previous_install_to_restore(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        staging = self._staged(tmp_path)
        target = tmp_path / "install"
        monkeypatch.setattr(Path, "rename", _raise_rename)
        monkeypatch.setattr("installer.ops.staging.shutil.copytree", _raise_copytree)

        with pytest.raises(OSError):
            swap_in_bundle(staging, target)

        assert not target.exists()

    def test_a_restore_that_also_fails_leaves_the_original_error_standing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The caller is already raising; a second failure must not mask it."""
        staging = self._staged(tmp_path)
        target = tmp_path / "install"
        target.mkdir()
        original = Path.rename
        moves: list[int] = []

        def _only_the_first_move_works(self: Path, *args: object) -> None:
            moves.append(1)
            if len(moves) == 1:
                return original(self, *args)
            raise OSError("no")

        monkeypatch.setattr(Path, "rename", _only_the_first_move_works)
        monkeypatch.setattr("installer.ops.staging.shutil.copytree", _raise_copytree)

        with pytest.raises(OSError, match="copy failed"):
            swap_in_bundle(staging, target)


def _raise_copytree(*args: object, **kwargs: object) -> None:
    """Stand in for a copytree that cannot complete."""
    raise OSError("copy failed")


def _raise_rename(self: Path, *args: object) -> None:
    """Stand in for a rename that cannot complete."""
    raise OSError("rename failed")


class TestInstalledExe:
    def test_it_names_the_executable_inside_an_install(self, tmp_path: Path) -> None:
        assert installed_exe(tmp_path).parent == tmp_path


class TestCopySelfToInstall:
    def test_it_places_a_copy_of_the_setup_program_under_the_install(
        self, scratch_identity: InstallerIdentity, tmp_path: Path
    ) -> None:
        install_dir = tmp_path / "install"
        install_dir.mkdir()

        copied = copy_self_to_install(scratch_identity, install_dir)

        assert copied == scratch_identity.installer_exe_path(install_dir.resolve())
        assert copied.is_file()
        assert copied.stat().st_size == Path(sys.executable).stat().st_size


class TestDisplayIcon:
    def test_the_deployed_ico_is_preferred(self, tmp_path: Path) -> None:
        (tmp_path / APP_ICO_NAME).write_bytes(b"ico")

        assert display_icon_for(tmp_path) == str(tmp_path / APP_ICO_NAME)

    def test_without_an_ico_the_executable_carries_its_own(
        self, tmp_path: Path
    ) -> None:
        assert display_icon_for(tmp_path) == str(installed_exe(tmp_path))


class TestRegisterUninstall:
    def test_it_records_everything_apps_and_features_shows(
        self, scratch_identity: InstallerIdentity, tmp_path: Path
    ) -> None:
        install_dir = tmp_path / "install"
        install_dir.mkdir()
        installer_copy = install_dir / "_installer" / "Setup.exe"

        register_uninstall(
            scratch_identity,
            install_dir=install_dir,
            installer_copy=installer_copy,
            shortcut_desktop=True,
            shortcut_start_menu=False,
        )

        entry = read_uninstall_entry(scratch_identity.uninstall_key)
        assert entry is not None
        assert entry.display_name == APP_NAME
        assert entry.display_version == __version__
        assert entry.publisher == APP_AUTHOR
        assert entry.install_location == install_dir
        assert entry.uninstall_string == f'"{installer_copy}" {UNINSTALL_FLAG}'
        assert entry.shortcut_desktop is True
        assert entry.shortcut_start_menu is False


class TestDeployRuntimeIconAssets:
    def test_it_copies_the_icon_set_beside_the_executable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / APP_ICO_NAME).write_bytes(b"ico")
        for name in APP_ICON_PNG_NAMES:
            (source / name).write_bytes(b"png")
        install_dir = tmp_path / "install"
        install_dir.mkdir()
        monkeypatch.setattr(
            "installer.ops.registration.bundled_data_root", lambda: source
        )
        monkeypatch.setattr(
            "installer.ops.registration.find_app_icon_path",
            lambda *, project_root: source / APP_ICO_NAME,
        )

        deploy_runtime_icon_assets(install_dir=install_dir)

        assert (install_dir / APP_ICO_NAME).is_file()
        assert all((install_dir / name).is_file() for name in APP_ICON_PNG_NAMES)

    def test_no_icon_to_deploy_is_not_an_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        install_dir = tmp_path / "install"
        install_dir.mkdir()
        monkeypatch.setattr(
            "installer.ops.registration.bundled_data_root", lambda: tmp_path / "absent"
        )
        monkeypatch.setattr(
            "installer.ops.registration.find_app_icon_path",
            lambda *, project_root: None,
        )

        deploy_runtime_icon_assets(install_dir=install_dir)

        assert list(install_dir.iterdir()) == []

    def test_an_icon_that_cannot_be_copied_does_not_fail_the_install(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The files are already down by this point, so a missing icon is cosmetic."""
        source = tmp_path / "source"
        source.mkdir()
        (source / APP_ICO_NAME).write_bytes(b"ico")
        for name in APP_ICON_PNG_NAMES:
            (source / name).write_bytes(b"png")
        # A directory that does not exist, so no copy into it can succeed.
        install_dir = tmp_path / "absent"
        monkeypatch.setattr(
            "installer.ops.registration.bundled_data_root", lambda: source
        )
        monkeypatch.setattr(
            "installer.ops.registration.find_app_icon_path",
            lambda *, project_root: source / APP_ICO_NAME,
        )

        deploy_runtime_icon_assets(install_dir=install_dir)

        assert not install_dir.exists()
