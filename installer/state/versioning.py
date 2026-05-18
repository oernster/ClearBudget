"""Version parsing and comparison."""

from __future__ import annotations

from dataclasses import dataclass

from packaging.version import InvalidVersion, Version


@dataclass(frozen=True, slots=True)
class ParsedVersion:
    raw: str
    parsed: Version


def parse_version(version_str: str) -> ParsedVersion:
    v = (version_str or "").strip()
    try:
        return ParsedVersion(raw=v, parsed=Version(v))
    except InvalidVersion:
        # Fall back to 0.0.0 for unparseable strings; treat as very old.
        return ParsedVersion(raw=v, parsed=Version("0.0.0"))


def compare_versions(installer_version: str, installed_version: str) -> int:
    """Compare installer vs installed versions.

    Returns:
        -1 if installer < installed
         0 if equal
         1 if installer > installed
    """

    a = parse_version(installer_version).parsed
    b = parse_version(installed_version).parsed
    if a < b:
        return -1
    if a > b:
        return 1
    return 0
