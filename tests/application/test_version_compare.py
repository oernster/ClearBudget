"""Tests for the pure version comparison behind the update check."""

import pytest

from clear_budget.application.services.version_compare import is_newer


@pytest.mark.parametrize(
    "latest, current",
    [
        ("4.3.0", "4.2.0"),
        ("5.0.0", "4.9.9"),
        ("4.2.1", "4.2.0"),
        ("v4.3.0", "4.2.0"),
        ("V4.3.0", "4.2.0"),
        (" 4.3.0 ", "4.2.0"),
        ("4.2.0.1", "4.2.0"),
    ],
)
def test_a_strictly_newer_release_is_newer(latest, current):
    assert is_newer(latest, current) is True


@pytest.mark.parametrize(
    "latest, current",
    [
        ("4.2.0", "4.2.0"),
        ("v4.2.0", "4.2.0"),
        ("4.1.9", "4.2.0"),
        ("3.9.9", "4.0.0"),
    ],
)
def test_an_equal_or_older_release_is_not_newer(latest, current):
    assert is_newer(latest, current) is False


@pytest.mark.parametrize(
    "latest, current",
    [
        ("not-a-version", "4.2.0"),
        ("4.2.0", "not-a-version"),
        ("", "4.2.0"),
        ("4.2.0", ""),
        ("4.2.0-beta", "4.2.0"),
    ],
)
def test_a_malformed_version_never_reports_newer(latest, current):
    """A tag that cannot be parsed must never raise a spurious prompt."""
    assert is_newer(latest, current) is False
