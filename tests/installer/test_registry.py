"""The HKCU registration: what makes Clear Budget an installed program.

Every write goes to the scratch key the identity fixture yields and that key is
removed in teardown, so the user's own Apps and features entry is never read or
written. British spelling is used in comments.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from installer.constants import InstallerIdentity
from installer.state.registry import (
    delete_uninstall_entry,
    read_uninstall_entry,
    try_read_install_location,
    write_uninstall_entry,
)

_VERSION = "4.0.0"
_UNINSTALL_STRING = '"setup.exe" --uninstall'


def _write(key: str, location: Path, **extra: object) -> None:
    write_uninstall_entry(
        key,
        display_name="Clear Budget",
        display_version=_VERSION,
        install_location=location,
        uninstall_string=_UNINSTALL_STRING,
        **extra,
    )


@pytest.fixture()
def key(scratch_identity: InstallerIdentity) -> str:
    return scratch_identity.uninstall_key


class TestWriteAndRead:
    def test_it_records_what_apps_and_features_needs(
        self, key: str, tmp_path: Path
    ) -> None:
        _write(key, tmp_path)

        entry = read_uninstall_entry(key)

        assert entry is not None
        assert entry.display_name == "Clear Budget"
        assert entry.display_version == _VERSION
        assert entry.install_location == tmp_path
        assert entry.uninstall_string == _UNINSTALL_STRING

    def test_the_optional_values_are_recorded_when_given(
        self, key: str, tmp_path: Path
    ) -> None:
        _write(
            key,
            tmp_path,
            display_icon="icon.ico",
            publisher="Oliver Ernster",
            installer_path="setup.exe",
        )

        entry = read_uninstall_entry(key)

        assert entry is not None
        assert entry.display_icon == "icon.ico"
        assert entry.publisher == "Oliver Ernster"
        assert entry.installer_path == "setup.exe"

    def test_the_optional_values_are_absent_when_not_given(
        self, key: str, tmp_path: Path
    ) -> None:
        _write(key, tmp_path)

        entry = read_uninstall_entry(key)

        assert entry is not None
        assert entry.display_icon is None
        assert entry.publisher is None
        assert entry.shortcut_desktop is None

    @pytest.mark.parametrize(
        ("desktop", "start_menu"), [(True, False), (False, True), (True, True)]
    )
    def test_the_shortcut_choices_survive_a_round_trip(
        self, key: str, tmp_path: Path, desktop: bool, start_menu: bool
    ) -> None:
        _write(key, tmp_path, shortcut_desktop=desktop, shortcut_start_menu=start_menu)

        entry = read_uninstall_entry(key)

        assert entry is not None
        assert entry.shortcut_desktop is desktop
        assert entry.shortcut_start_menu is start_menu

    def test_an_unregistered_key_reads_as_not_installed(self, key: str) -> None:
        assert read_uninstall_entry(key) is None

    def test_an_entry_missing_its_required_values_reads_as_not_installed(
        self, key: str
    ) -> None:
        _write_values(key, {"DisplayName": "Clear Budget"})

        assert read_uninstall_entry(key) is None

    def test_a_relative_install_location_reads_as_not_installed(self, key: str) -> None:
        """Path('') is truthy and resolves to the working directory, which is
        the one place an uninstall must never point at."""
        _write_values(
            key,
            {
                "DisplayName": "Clear Budget",
                "InstallLocation": "relative/path",
                "UninstallString": _UNINSTALL_STRING,
            },
        )

        assert read_uninstall_entry(key) is None


class TestTryReadInstallLocation:
    def test_it_reads_a_location_even_when_the_rest_is_missing(
        self, key: str, tmp_path: Path
    ) -> None:
        _write_values(key, {"InstallLocation": str(tmp_path)})

        assert try_read_install_location(key) == tmp_path

    def test_an_absent_key_has_no_location(self, key: str) -> None:
        assert try_read_install_location(key) is None

    def test_a_key_without_the_value_has_no_location(self, key: str) -> None:
        _write_values(key, {"DisplayName": "Clear Budget"})

        assert try_read_install_location(key) is None


class TestDeleteUninstallEntry:
    def test_it_removes_the_registration(self, key: str, tmp_path: Path) -> None:
        _write(key, tmp_path)

        delete_uninstall_entry(key)

        assert read_uninstall_entry(key) is None

    def test_a_key_that_is_already_gone_is_not_an_error(self, key: str) -> None:
        delete_uninstall_entry(key)

    def test_a_key_that_cannot_be_removed_is_reported(
        self, key: str, tmp_path: Path
    ) -> None:
        """A key with children cannot be deleted; that is not the same as
        the key being absent, so it is raised rather than swallowed."""
        _write(key, tmp_path)
        _write_values(rf"{key}\Child", {"Value": "x"})

        with pytest.raises(OSError):
            delete_uninstall_entry(key)


class TestWindowsOnly:
    @pytest.mark.parametrize(
        "call",
        [
            lambda key: read_uninstall_entry(key),
            lambda key: try_read_install_location(key),
            lambda key: delete_uninstall_entry(key),
        ],
    )
    def test_the_registry_is_not_touched_off_windows(
        self, key: str, monkeypatch: pytest.MonkeyPatch, call
    ) -> None:
        monkeypatch.setattr(os, "name", "posix")

        with pytest.raises(RuntimeError):
            call(key)

    def test_writing_is_refused_off_windows(
        self, key: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(os, "name", "posix")

        with pytest.raises(RuntimeError):
            _write(key, tmp_path)


class TestParsingRecordedFlags:
    @pytest.mark.parametrize("raw", ["1", "true", "YES", "on"])
    def test_the_affirmative_spellings_read_as_true(self, key: str, raw: str) -> None:
        assert _round_trip_flag(key, raw) is True

    @pytest.mark.parametrize("raw", ["0", "false", "NO", "off"])
    def test_the_negative_spellings_read_as_false(self, key: str, raw: str) -> None:
        assert _round_trip_flag(key, raw) is False

    def test_anything_else_reads_as_unknown(self, key: str) -> None:
        assert _round_trip_flag(key, "perhaps") is None


def _round_trip_flag(key: str, raw: str) -> bool | None:
    """Record a raw ShortcutDesktop value and read back how it was parsed."""
    _write_values(
        key,
        {
            "DisplayName": "Clear Budget",
            "InstallLocation": str(Path.home()),
            "UninstallString": _UNINSTALL_STRING,
            "ShortcutDesktop": raw,
        },
    )
    entry = read_uninstall_entry(key)
    assert entry is not None
    return entry.shortcut_desktop


def _write_values(key: str, values: dict[str, str]) -> None:
    """Write raw string values, so a partial or odd entry can be exercised."""
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as handle:
        for name, value in values.items():
            winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, value)
