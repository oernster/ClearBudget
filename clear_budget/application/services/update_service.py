"""UpdateService: decide whether a newer release is available.

The service asks the injected ``ReleaseSource`` for the latest published
release and compares it against the running version. The one network call the
otherwise offline app makes happens indirectly through the source; the
service never raises for an unreachable source: the source returns None and
the service reports no update available. A release the user chose to skip is
reported as seen but not available, so the same version never prompts twice.

The service also picks the download for the running platform from the
release's assets by filename suffix, falling back to the release page when no
asset matches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from clear_budget.application.dto.update_info import UpdateStatus
from clear_budget.application.services.version_compare import is_newer

if TYPE_CHECKING:
    from clear_budget.application.dto.update_info import ReleaseAsset
    from clear_budget.application.ports.release_source import ReleaseSource

__all__ = [
    "PLATFORM_LINUX",
    "PLATFORM_MACOS",
    "PLATFORM_WINDOWS",
    "UpdateService",
    "platform_key_for",
    "select_asset_url",
]

# Platform keys naming which release asset the running OS wants.
PLATFORM_WINDOWS = "windows"
PLATFORM_MACOS = "macos"
PLATFORM_LINUX = "linux"

# Asset filename suffixes per platform, in preference order.
_ASSET_SUFFIXES = {
    PLATFORM_WINDOWS: (".exe",),
    PLATFORM_MACOS: (".dmg",),
    PLATFORM_LINUX: (".flatpak",),
}

# sys.platform values with a dedicated key; anything else is treated as Linux.
_SYS_PLATFORM_KEYS = {"win32": PLATFORM_WINDOWS, "darwin": PLATFORM_MACOS}


def platform_key_for(sys_platform: str) -> str:
    """Map a ``sys.platform`` value to a platform key."""
    return _SYS_PLATFORM_KEYS.get(sys_platform, PLATFORM_LINUX)


def select_asset_url(assets: tuple[ReleaseAsset, ...], platform_key: str) -> str | None:
    """Return the download URL of the first asset matching the platform."""
    for suffix in _ASSET_SUFFIXES.get(platform_key, ()):
        for asset in assets:
            if asset.name.lower().endswith(suffix):
                return asset.download_url
    return None


class UpdateService:
    """Compares the running version against the latest published release."""

    def __init__(
        self, source: ReleaseSource, current_version: str, platform_key: str
    ) -> None:
        self._source = source
        self._current_version = current_version
        self._platform_key = platform_key

    def check(self, skipped_version: str | None = None) -> UpdateStatus:
        """Return the update status for the running version.

        A source that cannot be reached yields a None latest version and so a
        status reporting no update, keeping the check silent on failure. A
        newer release whose version equals ``skipped_version`` is reported
        with ``update_available`` False.
        """
        info = self._source.latest_release()
        if info is None:
            return UpdateStatus(
                current=self._current_version,
                latest=None,
                update_available=False,
                download_url=None,
                page_url=None,
            )
        newer = is_newer(info.version, self._current_version)
        available = newer and info.version != skipped_version
        return UpdateStatus(
            current=self._current_version,
            latest=info.version,
            update_available=available,
            download_url=select_asset_url(info.assets, self._platform_key),
            page_url=info.page_url,
        )
