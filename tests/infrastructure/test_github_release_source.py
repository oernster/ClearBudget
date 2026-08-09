"""Tests for the GitHub release adapter, with the HTTP opener faked."""

import json

import pytest

from clear_budget.application.dto.update_info import ReleaseAsset
from clear_budget.infrastructure.update.github_release_source import (
    LATEST_RELEASE_API_URL,
    GitHubReleaseSource,
)

_TAG = "4.3.0"
_PAGE_URL = "https://github.com/oernster/ClearBudget/releases/tag/4.3.0"


def _payload(**overrides):
    data = {
        "tag_name": _TAG,
        "html_url": _PAGE_URL,
        "assets": [
            {
                "name": "ClearBudgetSetup.exe",
                "browser_download_url": "https://dl/setup.exe",
            },
            {"name": "ClearBudget.dmg", "browser_download_url": "https://dl/app.dmg"},
        ],
    }
    data.update(overrides)
    return data


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener_returning(body: bytes, seen: list | None = None):
    def opener(request, timeout):
        if seen is not None:
            seen.append((request, timeout))
        return _FakeResponse(body)

    return opener


def _source_for(data, seen=None):
    body = json.dumps(data).encode("utf-8")
    return GitHubReleaseSource(opener=_opener_returning(body, seen))


def test_a_published_release_is_read_with_its_assets():
    info = _source_for(_payload()).latest_release()
    assert info is not None
    assert info.version == _TAG
    assert info.page_url == _PAGE_URL
    assert info.assets == (
        ReleaseAsset(name="ClearBudgetSetup.exe", download_url="https://dl/setup.exe"),
        ReleaseAsset(name="ClearBudget.dmg", download_url="https://dl/app.dmg"),
    )


def test_the_request_targets_the_latest_release_endpoint_as_json():
    seen = []
    _source_for(_payload(), seen=seen).latest_release()
    request, timeout = seen[0]
    assert request.full_url == LATEST_RELEASE_API_URL
    assert request.get_header("Accept") == "application/vnd.github+json"
    assert timeout == 5.0


def test_a_failing_opener_yields_none():
    def opener(request, timeout):
        raise OSError("no network")

    assert GitHubReleaseSource(opener=opener).latest_release() is None


def test_an_unparseable_body_yields_none():
    source = GitHubReleaseSource(opener=_opener_returning(b"not json"))
    assert source.latest_release() is None


def test_a_non_object_body_yields_none():
    assert _source_for(["a", "list"]).latest_release() is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"tag_name": None},
        {"tag_name": ""},
        {"tag_name": 430},
        {"html_url": None},
        {"html_url": ""},
    ],
)
def test_a_payload_missing_its_identity_yields_none(overrides):
    assert _source_for(_payload(**overrides)).latest_release() is None


@pytest.mark.parametrize("assets", [None, "not-a-list", {}])
def test_a_malformed_assets_field_reads_as_no_assets(assets):
    info = _source_for(_payload(assets=assets)).latest_release()
    assert info is not None
    assert info.assets == ()


def test_malformed_asset_entries_are_filtered_out():
    assets = [
        "not-a-dict",
        {"name": "no-url.exe"},
        {"name": "", "browser_download_url": "https://dl/empty-name"},
        {"name": "bad-url.exe", "browser_download_url": 7},
        {"name": "good.exe", "browser_download_url": "https://dl/good.exe"},
    ]
    info = _source_for(_payload(assets=assets)).latest_release()
    assert info is not None
    assert info.assets == (
        ReleaseAsset(name="good.exe", download_url="https://dl/good.exe"),
    )
