"""Fixtures that keep the installer suite off the real machine.

The setup program does the most privileged work in this repository: it writes
the HKCU registration, creates shortcuts in the user's profile, deploys a
bundle and deletes directories. Four isolations, each autouse and
unconditional, because the alternative is remembering:

  * the HKCU keys the installer writes come from an `InstallerIdentity`, so
    every test is given a scratch identity under a test-only root and that key
    is removed afterwards;
  * the per-user locations come from environment variables, so the profile
    directories are redirected into a temporary tree;
  * the platformdirs lookups the legacy migration makes do NOT read those
    variables, so they are redirected in their own right;
  * the real payload is over fifty megabytes, so the payload anchor is
    redirected and a small bundle stands in for it.

Between them, running this suite never reads or writes an actual Clear Budget
installation. British spelling is used in comments.
"""

from __future__ import annotations

import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from installer.constants import (
    APP_EXE_NAME,
    APP_INTERNAL_DIR_NAME,
    ENV_APPDATA,
    ENV_LOCALAPPDATA,
    InstallerIdentity,
)
from installer.ops import legacy as legacy_module
from installer.ops import payload as payload_module

TEST_KEY_ROOT = r"Software\ClearBudgetInstallerTests"
_USER_PROFILE = "USERPROFILE"
_HOME = "HOME"

PAYLOAD_ZIP_NAME = "payload.zip"
MANIFEST_JSON_NAME = "manifest.json"

# What the stand-in bundle contains: the executable the install checks for, the
# directory beside it and one nested file, which is enough to exercise the
# member walk, the nested-directory creation and the manifest repair.
BUNDLE_EXE_BYTES = b"executable"
BUNDLE_NESTED_PATH = f"{APP_INTERNAL_DIR_NAME}/base_library.zip"
BUNDLE_NESTED_BYTES = b"library"


def delete_tree(key: str) -> None:
    """Remove an HKCU key and everything under it."""
    import winreg

    try:
        handle = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key)
    except OSError:
        return
    with handle:
        while True:
            try:
                child = winreg.EnumKey(handle, 0)
            except OSError:
                break
            delete_tree(rf"{key}\{child}")
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
    except OSError:
        return


@pytest.fixture()
def scratch_identity() -> Iterator[InstallerIdentity]:
    """Yield an identity whose registry key is scratch, removed afterwards."""
    root = rf"{TEST_KEY_ROOT}\{uuid.uuid4().hex}"
    identity = InstallerIdentity(
        uninstall_key=rf"{root}\Uninstall",
        uninstall_key_name="ClearBudgetTest",
        start_menu_folder="ClearBudgetTest",
        shortcut_name="ClearBudgetTest",
    )
    try:
        yield identity
    finally:
        delete_tree(root)


@pytest.fixture(autouse=True)
def isolated_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect every per-user location into a temporary tree.

    Autouse because a shortcut written to the real Desktop or a log written to
    the real AppData is a change the user sees; no test needs either.
    """
    home = tmp_path / "profile"
    (home / "Desktop").mkdir(parents=True)
    local = home / "AppData" / "Local"
    roaming = home / "AppData" / "Roaming"
    local.mkdir(parents=True)
    roaming.mkdir(parents=True)

    monkeypatch.setenv(_USER_PROFILE, str(home))
    monkeypatch.setenv(_HOME, str(home))
    monkeypatch.setenv(ENV_LOCALAPPDATA, str(local))
    monkeypatch.setenv(ENV_APPDATA, str(roaming))
    return home


@pytest.fixture(autouse=True)
def isolated_platformdirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect the platformdirs lookups the legacy migration makes.

    platformdirs asks Windows for the known folder rather than reading
    %LOCALAPPDATA%, so redirecting the environment is not enough on its own:
    without this, a test that runs an install would move the real per-user data
    directory of anyone who still has the pre-rename one.
    """
    root = tmp_path / "platformdirs"

    def _fake(kind: str):
        def _dir(appname: str, appauthor: str) -> str:
            return str(root / kind / appauthor / appname)

        return _dir

    monkeypatch.setattr(legacy_module, "user_data_dir", _fake("data"))
    monkeypatch.setattr(legacy_module, "user_cache_dir", _fake("cache"))
    return root


@pytest.fixture(autouse=True)
def staged_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the payload anchor at a temporary tree holding a small bundle.

    Autouse because the real payload is over fifty megabytes: a test that
    extracted it by accident would be slow enough to look like a hang, and
    would deploy the actual application into a temporary directory.
    """
    root = tmp_path / "resources"
    payload_dir = root / "installer" / "payload"
    payload_dir.mkdir(parents=True)
    monkeypatch.setattr(payload_module, "resource_path", lambda rel: root / rel)
    write_bundle(payload_dir / PAYLOAD_ZIP_NAME)
    return payload_dir


def write_bundle(archive: Path, *, extra: dict[str, bytes] | None = None) -> Path:
    """Write a small stand-in for the application bundle."""
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(APP_EXE_NAME, BUNDLE_EXE_BYTES)
        bundle.writestr(BUNDLE_NESTED_PATH, BUNDLE_NESTED_BYTES)
        for name, data in (extra or {}).items():
            bundle.writestr(name, data)
    return archive
