"""GitHubReleaseSource: read the latest published release from the GitHub API.

This adapter implements the application ``ReleaseSource`` port. It performs a
single short, best-effort HTTPS GET against GitHub's latest-release endpoint
using only the standard library (``urllib``), so the otherwise offline app
gains no third-party runtime dependency for one network call. Any failure (no
network, a timeout, a non-2xx status or an unparseable body) yields None, so
the update check is non-blocking and silent on failure.

The latest-release endpoint only ever reports a published, non-draft,
non-prerelease release, so a tag pushed mid-development can never raise an
update prompt: the guard is the endpoint's own contract, not a check here.

The HTTP opener is injected (defaulting to ``urllib.request.urlopen``) so the
adapter can be tested without touching the network.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Any

from clear_budget.application.dto.update_info import ReleaseAsset, ReleaseInfo

__all__ = ["GitHubReleaseSource", "LATEST_RELEASE_API_URL"]

# GitHub's latest-release endpoint for this repository: published releases
# only, so drafts, prereleases and bare tags are structurally invisible.
LATEST_RELEASE_API_URL = (
    "https://api.github.com/repos/oernster/ClearBudget/releases/latest"
)

# Fields in the GitHub "latest release" payload.
_TAG_NAME_FIELD = "tag_name"
_PAGE_URL_FIELD = "html_url"
_ASSETS_FIELD = "assets"
_ASSET_NAME_FIELD = "name"
_ASSET_URL_FIELD = "browser_download_url"
# Header advertising a JSON client to the GitHub API.
_ACCEPT_HEADER = "Accept"
_ACCEPT_JSON = "application/vnd.github+json"
# A short timeout (seconds): the check must never block the app for long.
_TIMEOUT_S = 5.0
# Response encoding for the JSON body.
_ENCODING = "utf-8"


def _parse_assets(raw: Any) -> tuple[ReleaseAsset, ...]:
    """Return the well-formed assets from the payload's assets list."""
    if not isinstance(raw, list):
        return ()
    assets = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get(_ASSET_NAME_FIELD)
        url = entry.get(_ASSET_URL_FIELD)
        if isinstance(name, str) and name and isinstance(url, str) and url:
            assets.append(ReleaseAsset(name=name, download_url=url))
    return tuple(assets)


class GitHubReleaseSource:
    """A ``ReleaseSource`` backed by the GitHub latest-release endpoint."""

    def __init__(
        self,
        api_url: str = LATEST_RELEASE_API_URL,
        opener: Callable[..., Any] = urllib.request.urlopen,
        timeout_s: float = _TIMEOUT_S,
    ) -> None:
        self._api_url = api_url
        self._opener = opener
        self._timeout_s = timeout_s

    def latest_release(self) -> ReleaseInfo | None:
        """Return the latest published release or None when it cannot be read."""
        request = urllib.request.Request(
            self._api_url, headers={_ACCEPT_HEADER: _ACCEPT_JSON}
        )
        try:
            with self._opener(request, timeout=self._timeout_s) as response:
                payload = response.read()
            data = json.loads(payload.decode(_ENCODING))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        tag = data.get(_TAG_NAME_FIELD)
        page_url = data.get(_PAGE_URL_FIELD)
        if not (
            isinstance(tag, str) and tag and isinstance(page_url, str) and page_url
        ):
            return None
        return ReleaseInfo(
            version=tag,
            page_url=page_url,
            assets=_parse_assets(data.get(_ASSETS_FIELD)),
        )
