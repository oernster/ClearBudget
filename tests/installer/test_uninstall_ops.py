"""Uninstall: shortcuts, registration and then the files.

The detached PowerShell helper is observed through the recording runner rather
than started, so no test schedules a real deletion. British spelling is used in
comments.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from installer.constants import APP_EXE_NAME, InstallerIdentity
from installer.ops.errors import AppRunningError, InstallerOperationError
from installer.ops.install_ops import InstallOptions, install_new
from installer.ops.progress import (
    COMPLETE_PCT,
    READ_METADATA_PCT,
    REMOVE_FILES_PCT,
    REMOVE_REGISTRY_PCT,
    REMOVE_SHORTCUTS_PCT,
)
from installer.ops.removal import (
    DEFERRED_DELETE_ATTEMPTS,
    DIRECT_DELETE_ATTEMPTS,
    deferred_delete_script,
    delete_install_dir_now,
    remove_install_dir,
    running_from_inside,
    schedule_delete_after_exit,
)
from installer.ops.shortcuts import get_shortcut_paths
from installer.ops.uninstall_ops import (
    NOT_INSTALLED_MESSAGE,
    WINDOWS_ONLY_MESSAGE,
    UninstallOptions,
    uninstall,
    uninstall_with_feedback,
)
from installer.state.registry import read_uninstall_entry, write_uninstall_entry
from tests.installer.fakes import (
    CancelledEvent,
    FakeProcessController,
    FakeRunner,
    RecordingProgress,
)

_PID = 777
_QUOTED_DIR_NAME = "Oliver's Programs"


@pytest.fixture()
def installed(scratch_identity: InstallerIdentity, tmp_path: Path) -> Path:
    """Install once, so an uninstall has something to remove."""
    target = tmp_path / "programs" / "ClearBudget"
    install_new(
        scratch_identity,
        InstallOptions(
            target_dir=target,
            create_desktop_shortcut=True,
            create_start_menu_shortcut=True,
        ),
        controller=FakeProcessController(),
    )
    return target


class TestRunningFromInside:
    def test_an_installer_run_from_elsewhere_deletes_in_place(
        self, tmp_path: Path
    ) -> None:
        assert running_from_inside(tmp_path) is False

    def test_an_installer_living_inside_the_directory_defers(self) -> None:
        assert running_from_inside(Path(sys.executable).resolve().parent) is True


class TestDeferredDeleteScript:
    def test_it_polls_rather_than_sleeping_once(self, tmp_path: Path) -> None:
        script = deferred_delete_script(tmp_path)

        assert f"$i -lt {DEFERRED_DELETE_ATTEMPTS}" in script
        assert "Remove-Item" in script
        assert str(tmp_path) in script

    def test_a_quote_in_the_path_is_escaped(self, tmp_path: Path) -> None:
        """An unescaped apostrophe would end the string and break the script."""
        directory = tmp_path / _QUOTED_DIR_NAME

        script = deferred_delete_script(directory)

        assert "Oliver''s Programs" in script


class TestScheduleDeleteAfterExit:
    def test_it_starts_a_hidden_detached_helper(self, tmp_path: Path) -> None:
        runner = FakeRunner()

        schedule_delete_after_exit(tmp_path, runner)

        assert len(runner.detached) == 1
        args, _cwd = runner.detached[0]
        assert args[0].startswith("powershell")
        assert "Hidden" in args
        assert str(tmp_path.resolve()) in args[-1]


class TestDeleteInstallDirNow:
    def test_it_removes_the_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "install"
        target.mkdir()

        delete_install_dir_now(target)

        assert not target.exists()

    def test_a_directory_that_has_already_gone_is_not_an_error(
        self, tmp_path: Path
    ) -> None:
        delete_install_dir_now(tmp_path / "absent")

    def test_a_locked_directory_is_retried_and_then_reported(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "install"
        target.mkdir()
        held = (target / "locked.txt").open("w", encoding="utf-8")
        waits: list[float] = []
        try:
            with pytest.raises(InstallerOperationError, match="Could not remove"):
                delete_install_dir_now(target, sleep=waits.append)
        finally:
            held.close()

        assert len(waits) == DIRECT_DELETE_ATTEMPTS - 1


class TestRemoveInstallDir:
    def test_a_directory_the_installer_is_outside_of_goes_at_once(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "install"
        target.mkdir()
        runner = FakeRunner()

        remove_install_dir(target, runner)

        assert not target.exists()
        assert runner.detached == []

    def test_a_directory_holding_the_running_installer_is_deferred(self) -> None:
        runner = FakeRunner()

        remove_install_dir(Path(sys.executable).resolve().parent, runner)

        assert len(runner.detached) == 1


class TestUninstall:
    def test_it_removes_the_files_the_shortcuts_and_the_registration(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        paths = get_shortcut_paths(scratch_identity)

        uninstall(
            scratch_identity,
            UninstallOptions(),
            controller=FakeProcessController(),
            runner=FakeRunner(),
        )

        assert not installed.exists()
        assert not paths.desktop_lnk.exists()
        assert not paths.start_menu_lnk.exists()
        assert read_uninstall_entry(scratch_identity.uninstall_key) is None

    def test_it_reports_a_percentage_for_every_phase(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        """The bar used to sit at zero throughout; now each phase moves it."""
        progress = RecordingProgress()

        uninstall(
            scratch_identity,
            UninstallOptions(),
            progress=progress,
            controller=FakeProcessController(),
            runner=FakeRunner(),
        )

        assert progress.percentages == [
            READ_METADATA_PCT,
            REMOVE_SHORTCUTS_PCT,
            REMOVE_REGISTRY_PCT,
            REMOVE_FILES_PCT,
            COMPLETE_PCT,
        ]

    def test_a_shortcut_the_install_never_made_is_not_removed(
        self, scratch_identity: InstallerIdentity, tmp_path: Path
    ) -> None:
        """The recorded flags say which shortcuts were ours to remove."""
        target = tmp_path / "programs" / "ClearBudget"
        target.mkdir(parents=True)
        write_uninstall_entry(
            scratch_identity.uninstall_key,
            display_name="ClearBudget",
            display_version="4.0.0",
            install_location=target,
            uninstall_string="setup --uninstall",
            shortcut_desktop=False,
            shortcut_start_menu=False,
        )
        paths = get_shortcut_paths(scratch_identity)
        paths.desktop_lnk.parent.mkdir(parents=True, exist_ok=True)
        paths.desktop_lnk.write_bytes(b"not ours")

        uninstall(
            scratch_identity,
            UninstallOptions(),
            controller=FakeProcessController(),
            runner=FakeRunner(),
        )

        assert paths.desktop_lnk.is_file()

    def test_an_unreadable_entry_still_removes_both_shortcuts(
        self, scratch_identity: InstallerIdentity, tmp_path: Path
    ) -> None:
        """Nothing recorded, so remove both: a leftover launcher is worse."""
        target = tmp_path / "programs" / "ClearBudget"
        target.mkdir(parents=True)
        _write_location_only(scratch_identity.uninstall_key, target)
        paths = get_shortcut_paths(scratch_identity)
        paths.desktop_lnk.parent.mkdir(parents=True, exist_ok=True)
        paths.desktop_lnk.write_bytes(b"lnk")

        uninstall(
            scratch_identity,
            UninstallOptions(),
            controller=FakeProcessController(),
            runner=FakeRunner(),
        )

        assert not paths.desktop_lnk.exists()

    def test_it_refuses_when_nothing_is_registered(
        self, scratch_identity: InstallerIdentity
    ) -> None:
        with pytest.raises(InstallerOperationError, match=NOT_INSTALLED_MESSAGE):
            uninstall(
                scratch_identity,
                UninstallOptions(),
                controller=FakeProcessController(),
                runner=FakeRunner(),
            )

    def test_a_registration_pointing_at_a_directory_that_has_gone_still_cleans_up(
        self, scratch_identity: InstallerIdentity, tmp_path: Path
    ) -> None:
        target = tmp_path / "programs" / "gone"
        write_uninstall_entry(
            scratch_identity.uninstall_key,
            display_name="ClearBudget",
            display_version="4.0.0",
            install_location=target,
            uninstall_string="setup --uninstall",
        )

        uninstall(
            scratch_identity,
            UninstallOptions(),
            controller=FakeProcessController(),
            runner=FakeRunner(),
        )

        assert read_uninstall_entry(scratch_identity.uninstall_key) is None

    def test_a_registration_that_will_not_delete_does_not_block_the_removal(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        """Refusing to uninstall over a stubborn key would leave the user with
        no way to remove the program at all."""
        _write_values(rf"{scratch_identity.uninstall_key}\Child", {"Value": "x"})

        uninstall(
            scratch_identity,
            UninstallOptions(),
            controller=FakeProcessController(),
            runner=FakeRunner(),
        )

        assert not installed.exists()

    def test_it_refuses_while_the_application_is_running(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        exe = installed / APP_EXE_NAME

        with pytest.raises(AppRunningError):
            uninstall(
                scratch_identity,
                UninstallOptions(),
                controller=FakeProcessController(exe, [_PID]),
                runner=FakeRunner(),
            )

        assert installed.exists()

    def test_a_cancel_stops_it_before_anything_is_removed(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        with pytest.raises(InstallerOperationError, match="Cancelled"):
            uninstall(
                scratch_identity,
                UninstallOptions(),
                cancel_event=CancelledEvent(),
                controller=FakeProcessController(),
                runner=FakeRunner(),
            )

        assert installed.exists()

    def test_it_is_windows_only(
        self, scratch_identity: InstallerIdentity, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(os, "name", "posix")

        with pytest.raises(InstallerOperationError, match=WINDOWS_ONLY_MESSAGE):
            uninstall(scratch_identity, UninstallOptions())


class TestUninstallWithFeedback:
    def test_it_runs_the_uninstall_and_reports_as_it_goes(
        self, scratch_identity: InstallerIdentity, installed: Path
    ) -> None:
        progress = RecordingProgress()

        uninstall_with_feedback(
            scratch_identity,
            UninstallOptions(),
            progress=progress,
            controller=FakeProcessController(),
            runner=FakeRunner(),
        )

        assert not installed.exists()
        assert progress.percentages[-1] == COMPLETE_PCT


def _write_location_only(uninstall_key: str, location: Path) -> None:
    """Record an InstallLocation and nothing else, as a damaged entry would."""
    _write_values(uninstall_key, {"InstallLocation": str(location)})


def _write_values(key: str, values: dict[str, str]) -> None:
    """Write raw string values, so a partial or odd entry can be exercised."""
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as handle:
        for name, value in values.items():
            winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, value)
