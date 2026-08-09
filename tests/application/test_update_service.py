"""Tests for the update service: availability, skipping and asset choice."""

import pytest

from clear_budget.application.dto.update_info import ReleaseAsset, ReleaseInfo
from clear_budget.application.services.update_service import (
    PLATFORM_LINUX,
    PLATFORM_MACOS,
    PLATFORM_WINDOWS,
    UpdateService,
    platform_key_for,
    select_asset_url,
)

_CURRENT = "4.2.0"
_NEWER = "4.3.0"
_PAGE_URL = "https://github.com/oernster/ClearBudget/releases/tag/4.3.0"

_ASSETS = (
    ReleaseAsset(name="ClearBudgetSetup.exe", download_url="https://dl/setup.exe"),
    ReleaseAsset(name="ClearBudget.dmg", download_url="https://dl/app.dmg"),
    ReleaseAsset(name="ClearBudget.flatpak", download_url="https://dl/app.flatpak"),
)


class _FakeSource:
    """A ReleaseSource returning a canned release (or None)."""

    def __init__(self, info):
        self._info = info

    def latest_release(self):
        return self._info


def _release(version=_NEWER, assets=_ASSETS):
    return ReleaseInfo(version=version, page_url=_PAGE_URL, assets=assets)


def _service(info, platform_key=PLATFORM_WINDOWS):
    return UpdateService(
        source=_FakeSource(info),
        current_version=_CURRENT,
        platform_key=platform_key,
    )


def test_an_unreachable_source_reports_no_update():
    status = _service(None).check()
    assert status.current == _CURRENT
    assert status.latest is None
    assert status.update_available is False
    assert status.download_url is None
    assert status.page_url is None


def test_a_newer_release_is_available_with_its_download_and_page():
    status = _service(_release()).check()
    assert status.update_available is True
    assert status.latest == _NEWER
    assert status.download_url == "https://dl/setup.exe"
    assert status.page_url == _PAGE_URL


def test_the_running_version_is_not_an_update():
    status = _service(_release(version=_CURRENT)).check()
    assert status.update_available is False
    assert status.latest == _CURRENT


def test_a_skipped_release_is_seen_but_not_available():
    status = _service(_release()).check(skipped_version=_NEWER)
    assert status.update_available is False
    assert status.latest == _NEWER


def test_a_skip_of_some_other_release_does_not_suppress_the_prompt():
    status = _service(_release()).check(skipped_version="4.2.5")
    assert status.update_available is True


@pytest.mark.parametrize(
    "platform_key, expected",
    [
        (PLATFORM_WINDOWS, "https://dl/setup.exe"),
        (PLATFORM_MACOS, "https://dl/app.dmg"),
        (PLATFORM_LINUX, "https://dl/app.flatpak"),
    ],
)
def test_each_platform_picks_its_own_asset(platform_key, expected):
    assert select_asset_url(_ASSETS, platform_key) == expected


def test_asset_matching_ignores_case():
    assets = (ReleaseAsset(name="SETUP.EXE", download_url="https://dl/x"),)
    assert select_asset_url(assets, PLATFORM_WINDOWS) == "https://dl/x"


def test_a_release_with_no_matching_asset_yields_no_download_url():
    assert select_asset_url((), PLATFORM_WINDOWS) is None
    status = _service(_release(assets=())).check()
    assert status.update_available is True
    assert status.download_url is None
    assert status.page_url == _PAGE_URL


def test_an_unknown_platform_key_yields_no_download_url():
    assert select_asset_url(_ASSETS, "beos") is None


@pytest.mark.parametrize(
    "sys_platform, expected",
    [
        ("win32", PLATFORM_WINDOWS),
        ("darwin", PLATFORM_MACOS),
        ("linux", PLATFORM_LINUX),
        ("freebsd14", PLATFORM_LINUX),
    ],
)
def test_sys_platform_maps_to_a_platform_key(sys_platform, expected):
    assert platform_key_for(sys_platform) == expected
