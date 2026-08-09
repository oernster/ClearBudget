"""DTOs for the update check: the latest release and the check outcome.

``ReleaseInfo`` is what the release source hands back: the released version,
the release page and the downloadable assets. ``UpdateStatus`` is what the
``UpdateService`` hands the ui: whether a newer release exists and where the
platform's download lives when it does. ``latest`` is None when the source
could not be reached, in which case ``update_available`` is always False.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ReleaseAsset", "ReleaseInfo", "UpdateStatus"]


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    """One downloadable file attached to a release."""

    name: str
    download_url: str


@dataclass(frozen=True, slots=True)
class ReleaseInfo:
    """The latest published release as reported by the release source."""

    version: str
    page_url: str
    assets: tuple[ReleaseAsset, ...]


@dataclass(frozen=True, slots=True)
class UpdateStatus:
    """The result of comparing the running version against the latest release."""

    current: str
    latest: str | None
    update_available: bool
    download_url: str | None
    page_url: str | None
