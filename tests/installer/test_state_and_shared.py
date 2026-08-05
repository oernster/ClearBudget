"""Version comparison, the state model, the resource anchor and the log.

These are the Qt-free pieces the window reads before it decides what to offer.
British spelling is used in comments.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from installer.cli import parse_args
from installer.constants import (
    INSTALLER_DIR_NAME,
    MANIFEST_JSON_RESOURCE,
    PAYLOAD_ZIP_RESOURCE,
    InstallerIdentity,
)
from installer.shared.logging_setup import (
    installer_log_dir,
    installer_log_path,
    setup_installer_logging,
)
from installer.shared.resource_path import bundled_data_root, resource_path
from installer.state.model import InstalledInfo, InstallerState, Operation
from installer.state.versioning import compare_versions, parse_version

_OLDER = "1.0.0"
_CURRENT = "2.0.0"
_NEWER = "3.0.0"


class TestParseVersion:
    def test_a_semantic_version_parses(self) -> None:
        assert str(parse_version(_CURRENT).parsed) == _CURRENT

    def test_surrounding_whitespace_is_ignored(self) -> None:
        assert parse_version(f"  {_CURRENT}  ").raw == _CURRENT

    @pytest.mark.parametrize("raw", ["", "not-a-version"])
    def test_an_unparseable_version_is_treated_as_very_old(self, raw: str) -> None:
        """So an unreadable registration never blocks an upgrade."""
        assert compare_versions(_OLDER, raw) == 1


class TestCompareVersions:
    def test_a_newer_installer_compares_greater(self) -> None:
        assert compare_versions(_NEWER, _CURRENT) == 1

    def test_an_older_installer_compares_lesser(self) -> None:
        assert compare_versions(_OLDER, _CURRENT) == -1

    def test_the_same_version_compares_equal(self) -> None:
        assert compare_versions(_CURRENT, _CURRENT) == 0


class TestAllowedOperations:
    def _state(self, installed: str | None, tmp_path: Path) -> InstallerState:
        info = (
            None
            if installed is None
            else InstalledInfo(version=installed, location=tmp_path)
        )
        return InstallerState(installer_version=_CURRENT, installed=info)

    def test_nothing_installed_offers_only_install(self, tmp_path: Path) -> None:
        assert self._state(None, tmp_path).allowed_operations() == frozenset(
            {Operation.INSTALL}
        )

    def test_the_same_version_offers_reinstall_repair_and_uninstall(
        self, tmp_path: Path
    ) -> None:
        assert self._state(_CURRENT, tmp_path).allowed_operations() == frozenset(
            {Operation.REINSTALL, Operation.REPAIR, Operation.UNINSTALL}
        )

    def test_a_newer_installer_offers_upgrade(self, tmp_path: Path) -> None:
        assert self._state(_OLDER, tmp_path).allowed_operations() == frozenset(
            {Operation.UPGRADE, Operation.UNINSTALL}
        )

    def test_an_older_installer_never_offers_a_downgrade(self, tmp_path: Path) -> None:
        assert self._state(_NEWER, tmp_path).allowed_operations() == frozenset(
            {Operation.REPAIR, Operation.UNINSTALL}
        )


class TestStatusLine:
    def test_it_says_when_nothing_is_installed(self) -> None:
        state = InstallerState(installer_version=_CURRENT, installed=None)

        assert "not installed" in state.status_line("Clear Budget")

    def test_it_names_the_version_and_location_when_something_is(
        self, tmp_path: Path
    ) -> None:
        state = InstallerState(
            installer_version=_CURRENT,
            installed=InstalledInfo(version=_OLDER, location=tmp_path),
        )

        line = state.status_line("Clear Budget")

        assert _OLDER in line
        assert str(tmp_path) in line


class TestResourcePath:
    def test_the_anchor_is_the_repository_root_when_running_from_source(self) -> None:
        """The bug this replaced resolved one level above the repository."""
        root = bundled_data_root()

        assert (root / "installer" / "__init__.py").is_file()
        assert (root / "VERSION").is_file()

    def test_it_reads_the_meipass_root_in_a_frozen_build(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)

        assert bundled_data_root() == tmp_path

    @pytest.mark.parametrize("resource", [PAYLOAD_ZIP_RESOURCE, MANIFEST_JSON_RESOURCE])
    def test_a_resource_resolves_under_the_anchor(self, resource: str) -> None:
        assert resource_path(resource) == bundled_data_root() / resource


class TestInstallerLogging:
    def test_the_log_lands_under_the_redirected_profile(
        self, isolated_profile: Path
    ) -> None:
        assert isolated_profile in installer_log_dir().parents
        assert INSTALLER_DIR_NAME in installer_log_dir().parts

    def test_the_log_falls_back_when_local_appdata_is_unset(
        self, monkeypatch: pytest.MonkeyPatch, isolated_profile: Path
    ) -> None:
        monkeypatch.delenv("LOCALAPPDATA", raising=False)

        assert INSTALLER_DIR_NAME in installer_log_dir().parts

    def test_setting_it_up_creates_the_file_and_returns_its_path(self) -> None:
        handlers = list(logging.getLogger().handlers)
        try:
            path = setup_installer_logging()

            assert path == installer_log_path()
            assert path.is_file()
        finally:
            for handler in logging.getLogger().handlers:
                if handler not in handlers:
                    handler.close()
            logging.getLogger().handlers = handlers


class TestCommandLine:
    def test_no_arguments_runs_the_window(self) -> None:
        args = parse_args([])

        assert args.uninstall is False
        assert args.repair is False
        assert args.quiet is False

    @pytest.mark.parametrize(
        ("flag", "attribute"),
        [("--uninstall", "uninstall"), ("--repair", "repair"), ("--quiet", "quiet")],
    )
    def test_each_flag_is_recognised(self, flag: str, attribute: str) -> None:
        assert getattr(parse_args([flag]), attribute) is True


class TestInstallerIdentity:
    def test_the_uninstaller_copy_lives_under_the_install_root(
        self, tmp_path: Path
    ) -> None:
        identity = InstallerIdentity()

        path = identity.installer_exe_path(tmp_path)

        assert path.parent == tmp_path / identity.installer_subdir
        assert path.name == identity.installer_exe_name
