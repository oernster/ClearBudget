"""Writing the per-user shortcuts; clearing up after the app rename.

Shortcuts are written for real, through the same COM interface the install
uses, into the redirected profile: there is no value in a shortcut that is only
written in theory. The legacy helpers are pointed at the redirected profile and
the redirected platformdirs, so neither can touch a real installation. British
spelling is used in comments.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from clear_budget.version import APP_AUTHOR, APP_NAME, LEGACY_APP_NAME
from installer.constants import APP_EXE_NAME, APP_ICO_NAME, InstallerIdentity
from installer.ops import legacy as legacy_module
from installer.ops.errors import InstallerOperationError
from installer.ops.legacy import (
    local_appdata_root,
    migrate_legacy_appdata_dirs,
)
from installer.ops.shortcuts import (
    EMPTY_AUMID_MESSAGE,
    create_shortcut,
    get_shortcut_paths,
    icon_location_for,
    remove_shortcut,
    remove_taskbar_pin,
)

_MOVED_MARKER = "settings.json"


@pytest.fixture()
def exe(tmp_path: Path) -> Path:
    """Return an executable a shortcut can point at."""
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    path = install_dir / APP_EXE_NAME
    path.write_bytes(b"exe")
    return path


class TestShortcutPaths:
    def test_every_shortcut_lands_under_the_redirected_profile(
        self, scratch_identity: InstallerIdentity, isolated_profile: Path
    ) -> None:
        paths = get_shortcut_paths(scratch_identity)

        for link in (paths.desktop_lnk, paths.start_menu_lnk, paths.taskbar_lnk):
            assert isolated_profile in link.parents

    def test_the_start_menu_shortcut_sits_in_its_own_folder(
        self, scratch_identity: InstallerIdentity
    ) -> None:
        paths = get_shortcut_paths(scratch_identity)

        assert paths.start_menu_lnk.parent.name == scratch_identity.start_menu_folder

    def test_appdata_falls_back_when_the_variable_is_unset(
        self, scratch_identity: InstallerIdentity, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("APPDATA", raising=False)

        paths = get_shortcut_paths(scratch_identity)

        assert "Roaming" in paths.start_menu_lnk.parts

    def test_they_are_windows_only(
        self, scratch_identity: InstallerIdentity, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(os, "name", "posix")

        with pytest.raises(RuntimeError):
            get_shortcut_paths(scratch_identity)


class TestIconLocation:
    def test_the_deployed_ico_is_preferred_over_the_executable(self, exe: Path) -> None:
        ico = exe.parent / APP_ICO_NAME
        ico.write_bytes(b"ico")

        assert icon_location_for(exe) == str(ico.resolve())

    def test_without_one_the_executable_carries_its_own_icon(self, exe: Path) -> None:
        assert icon_location_for(exe) == str(exe)


class TestCreateShortcut:
    def test_it_writes_a_real_shortcut_file(self, exe: Path, tmp_path: Path) -> None:
        link = tmp_path / "links" / "Clear Budget.lnk"

        create_shortcut(exe, link, working_dir=exe.parent)

        assert link.is_file()
        assert link.stat().st_size > 0

    def test_it_writes_one_without_a_working_directory_too(
        self, exe: Path, tmp_path: Path
    ) -> None:
        link = tmp_path / "no-working-dir.lnk"

        create_shortcut(exe, link)

        assert link.is_file()

    def test_a_shortcut_that_cannot_be_saved_is_reported(
        self, exe: Path, tmp_path: Path
    ) -> None:
        blocked = tmp_path / "a-directory.lnk"
        blocked.mkdir()

        with pytest.raises(InstallerOperationError, match="Failed to create shortcut"):
            create_shortcut(exe, blocked)

    def test_an_empty_taskbar_identity_is_refused(
        self, exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without it Windows groups an installed launch separately from a pin."""
        monkeypatch.setattr("installer.ops.shortcuts.APP_APPUSERMODELID", "")

        with pytest.raises(InstallerOperationError, match=EMPTY_AUMID_MESSAGE):
            create_shortcut(exe, tmp_path / "link.lnk")

    def test_it_is_windows_only(
        self, exe: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(os, "name", "posix")

        with pytest.raises(RuntimeError):
            create_shortcut(exe, tmp_path / "link.lnk")


class TestRemoveShortcut:
    def test_it_deletes_the_file(self, tmp_path: Path) -> None:
        link = tmp_path / "links" / "link.lnk"
        link.parent.mkdir()
        link.write_bytes(b"lnk")

        remove_shortcut(link)

        assert not link.exists()

    def test_it_removes_a_start_menu_folder_it_has_emptied(
        self, tmp_path: Path
    ) -> None:
        link = tmp_path / "ClearBudget" / "link.lnk"
        link.parent.mkdir()
        link.write_bytes(b"lnk")

        remove_shortcut(link)

        assert not link.parent.exists()

    def test_it_leaves_a_folder_that_still_holds_something(
        self, tmp_path: Path
    ) -> None:
        link = tmp_path / "ClearBudget" / "link.lnk"
        link.parent.mkdir()
        link.write_bytes(b"lnk")
        (link.parent / "other.lnk").write_bytes(b"lnk")

        remove_shortcut(link)

        assert link.parent.is_dir()

    def test_a_shortcut_that_is_already_gone_is_not_an_error(
        self, tmp_path: Path
    ) -> None:
        remove_shortcut(tmp_path / "absent.lnk")

    def test_a_path_that_cannot_be_removed_is_left_alone(self, tmp_path: Path) -> None:
        directory = tmp_path / "a-directory"
        directory.mkdir()

        remove_shortcut(directory)

        assert directory.is_dir()

    def test_a_folder_that_cannot_be_removed_is_left_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Windows refuses to remove the working directory, so the shortcut
        goes and the folder stays rather than the removal failing."""
        folder = tmp_path / "ClearBudget"
        folder.mkdir()
        link = folder / "link.lnk"
        link.write_bytes(b"lnk")
        monkeypatch.chdir(folder)

        remove_shortcut(link)

        assert not link.exists()
        assert folder.is_dir()


class TestRemoveTaskbarPin:
    def test_it_deletes_the_pin(self, tmp_path: Path) -> None:
        pin = tmp_path / "pin.lnk"
        pin.write_bytes(b"lnk")

        remove_taskbar_pin(pin)

        assert not pin.exists()

    def test_a_pin_that_cannot_be_removed_is_not_an_error(self, tmp_path: Path) -> None:
        directory = tmp_path / "a-directory"
        directory.mkdir()

        remove_taskbar_pin(directory)

        assert directory.is_dir()


class TestLocalAppdataRoot:
    def test_it_reads_the_environment(self, isolated_profile: Path) -> None:
        assert local_appdata_root() == isolated_profile / "AppData" / "Local"

    def test_it_falls_back_when_the_variable_is_unset(
        self, monkeypatch: pytest.MonkeyPatch, isolated_profile: Path
    ) -> None:
        monkeypatch.delenv("LOCALAPPDATA", raising=False)

        assert local_appdata_root().parts[-2:] == ("AppData", "Local")


class TestMigrateLegacyAppdataDirs:
    def _old(self, root: Path, kind: str) -> Path:
        return root / kind / APP_AUTHOR / LEGACY_APP_NAME

    def _new(self, root: Path, kind: str) -> Path:
        return root / kind / APP_AUTHOR / APP_NAME

    def test_settings_under_the_old_name_move_forward(
        self, isolated_platformdirs: Path
    ) -> None:
        old = self._old(isolated_platformdirs, "data")
        old.mkdir(parents=True)
        (old / _MOVED_MARKER).write_text("kept", encoding="utf-8")

        migrate_legacy_appdata_dirs()

        moved = self._new(isolated_platformdirs, "data") / _MOVED_MARKER
        assert moved.read_text(encoding="utf-8") == "kept"
        assert not old.exists()

    def test_an_existing_new_directory_is_never_overwritten(
        self, isolated_platformdirs: Path
    ) -> None:
        old = self._old(isolated_platformdirs, "data")
        old.mkdir(parents=True)
        (old / _MOVED_MARKER).write_text("old", encoding="utf-8")
        new = self._new(isolated_platformdirs, "data")
        new.mkdir(parents=True)
        (new / _MOVED_MARKER).write_text("current", encoding="utf-8")

        migrate_legacy_appdata_dirs()

        assert (new / _MOVED_MARKER).read_text(encoding="utf-8") == "current"

    def test_nothing_to_migrate_is_not_an_error(
        self, isolated_platformdirs: Path
    ) -> None:
        migrate_legacy_appdata_dirs()

        assert not self._new(isolated_platformdirs, "data").exists()

    def test_a_migration_that_fails_leaves_the_install_to_carry_on(
        self, monkeypatch: pytest.MonkeyPatch, isolated_platformdirs: Path
    ) -> None:
        """A lost preference is not a reason to fail an install."""

        def _refuse(appname: str, appauthor: str) -> str:
            raise OSError("no such directory")

        monkeypatch.setattr(legacy_module, "user_data_dir", _refuse)

        migrate_legacy_appdata_dirs()


class TestNoStaleInstallCleanupExists:
    """The orphan-install tidy-up is gone and must stay gone.

    It rmtree'd `%LOCALAPPDATA%\\ClearBudget` as the pre-rename INSTALL
    directory; the app's DATA directory then moved to exactly that path and
    a setup run deleted live user data believing it was an orphaned install.
    """

    def test_the_legacy_install_cleanup_helper_no_longer_exists(self) -> None:
        assert not hasattr(legacy_module, "cleanup_orphaned_legacy_install")
