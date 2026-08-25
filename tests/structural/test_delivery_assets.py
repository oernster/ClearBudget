"""Every runtime asset reaches every platform the app ships on.

An icon added to the tree works immediately in a source run, because it sits
beside `main.py`. It goes MISSING in a packaged build unless it is staged in
each delivery script separately, where the failure is silent: the app launches,
the control wears no picture and the build reports success. That has happened
often enough to be worth a test rather than a habit.

Windows stages through `buildexe.py`, macOS through `builddmg.py`, Linux
through `build_flatpak.sh` TWICE over, once as a `sources:` entry that puts the
file in the build sandbox and once as a `cp` that installs it into the runtime
prefix. Missing either flatpak half is enough to lose the picture, so both are
asserted.

`ClearBudget.spec` is deliberately absent from this list: it is gitignored, so
it is not a shipped delivery path and would fail the test on a clean checkout.

The list under test is `resources._VIEW_ICON_NAMES`, which is the resolver's own
allowlist. That is the point: an asset the app can load at runtime is exactly
an asset a package has to carry, so the two cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clear_budget.shared.resources import _VIEW_ICON_NAMES

_ROOT = Path(__file__).resolve().parents[2]
_ASSETS = sorted(_VIEW_ICON_NAMES)


def _text(name: str) -> str:
    return (_ROOT / name).read_text(encoding="utf-8")


def _flatpak_install_lines() -> str:
    """The `cp` steps that put files into the runtime prefix."""
    return "\n".join(
        line
        for line in _text("build_flatpak.sh").splitlines()
        if line.strip().startswith("- cp ") and "/app/share/clearbudget" in line
    )


def _flatpak_source_lines() -> str:
    """The `path:` entries that put files into the build sandbox."""
    return "\n".join(
        line
        for line in _text("build_flatpak.sh").splitlines()
        if line.strip().startswith("path:")
    )


@pytest.mark.parametrize("asset", _ASSETS)
def test_the_asset_exists_on_disk(asset: str) -> None:
    """The allowlist naming a file that is not there is its own bug."""
    assert (_ROOT / asset).is_file(), f"{asset} is in the allowlist but not on disk"


@pytest.mark.parametrize("asset", _ASSETS)
def test_windows_stages_the_asset(asset: str) -> None:
    assert asset in _text("buildexe.py"), f"buildexe.py does not stage {asset}"


@pytest.mark.parametrize("asset", _ASSETS)
def test_macos_stages_the_asset(asset: str) -> None:
    assert asset in _text("builddmg.py"), f"builddmg.py does not stage {asset}"


@pytest.mark.parametrize("asset", _ASSETS)
def test_linux_copies_the_asset_into_the_prefix(asset: str) -> None:
    assert asset in _flatpak_install_lines(), (
        f"build_flatpak.sh never copies {asset} into /app/share/clearbudget, "
        "so the packaged app cannot resolve it"
    )


@pytest.mark.parametrize("asset", _ASSETS)
def test_linux_carries_the_asset_into_the_sandbox(asset: str) -> None:
    assert asset in _flatpak_source_lines(), (
        f"build_flatpak.sh has no sources entry for {asset}, so it is not in "
        "the build sandbox for the copy step to find"
    )


def test_the_guard_is_scanning_something() -> None:
    """Worthless if the allowlist empties or the flatpak sections are renamed."""
    assert len(_ASSETS) >= 5, f"only {len(_ASSETS)} assets found to check"
    assert _flatpak_install_lines(), "no flatpak cp lines matched"
    assert _flatpak_source_lines(), "no flatpak sources entries matched"


def test_the_macos_build_refuses_to_skip_a_missing_asset() -> None:
    """It used to `if asset.exists()` past one, shipping a blank control."""
    body = _text("builddmg.py")
    assert "raise SystemExit" in body
    assert "if asset.exists()" not in body
