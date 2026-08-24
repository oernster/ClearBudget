"""The single-instance lock, both platform branches, with hand-written fakes.

Two copies of the application open the same SQLite budget, so this lock is a
data guard rather than a nicety. Every platform detail is injected, so the
Windows branch is exercised on Linux and the POSIX branch on Windows.
"""

from __future__ import annotations

import pytest

from clear_budget.shared import single_instance


class FakeKernel32:
    """Just enough of the Win32 surface the lock uses."""

    def __init__(self, *, already_exists: bool) -> None:
        self._already_exists = already_exists
        self.created_with: tuple | None = None
        self.closed: list[int] = []
        self.handle = 4242

    def CreateMutexW(self, attributes, initial_owner, name):  # noqa: N802
        self.created_with = (attributes, initial_owner, name)
        return self.handle

    def GetLastError(self):  # noqa: N802
        return single_instance.WIN_ERROR_ALREADY_EXISTS if self._already_exists else 0

    def CloseHandle(self, handle):  # noqa: N802
        self.closed.append(handle)


class TestWindows:
    def test_a_free_mutex_yields_a_handle(self, tmp_path):
        kernel32 = FakeKernel32(already_exists=False)
        handle = single_instance.acquire(
            app_dir=tmp_path, platform="win32", kernel32=kernel32
        )
        assert handle == kernel32.handle
        assert kernel32.created_with == (None, True, single_instance.MUTEX_NAME)
        assert kernel32.closed == []

    def test_an_existing_mutex_yields_none_and_closes_the_handle(self, tmp_path):
        """The handle must be released; the loser otherwise leaks it for good."""
        kernel32 = FakeKernel32(already_exists=True)
        assert (
            single_instance.acquire(
                app_dir=tmp_path, platform="win32", kernel32=kernel32
            )
            is None
        )
        assert kernel32.closed == [kernel32.handle]


class TestPosix:
    def test_an_uncontended_lock_yields_an_open_file(self, tmp_path):
        taken: list[int] = []
        handle = single_instance.acquire(
            app_dir=tmp_path / "made" / "on" / "demand",
            platform="linux",
            flock=taken.append,
        )
        try:
            assert handle is not None
            assert not handle.closed
            assert len(taken) == 1
        finally:
            handle.close()

    def test_it_creates_the_data_directory_when_absent(self, tmp_path):
        target = tmp_path / "not" / "there" / "yet"
        handle = single_instance.acquire(
            app_dir=target, platform="linux", flock=lambda fd: None
        )
        try:
            assert (target / single_instance.LOCK_FILENAME).is_file()
        finally:
            handle.close()

    def test_a_contended_lock_yields_none_and_closes_the_file(self, tmp_path):
        """Leaving the file open would hold the lock the caller just lost."""

        def refuse(fd: int) -> None:
            raise OSError("already locked")

        assert (
            single_instance.acquire(app_dir=tmp_path, platform="darwin", flock=refuse)
            is None
        )
        # The file exists but nothing holds it, so a later attempt succeeds.
        assert (tmp_path / single_instance.LOCK_FILENAME).is_file()
        handle = single_instance.acquire(
            app_dir=tmp_path, platform="darwin", flock=lambda fd: None
        )
        try:
            assert handle is not None
        finally:
            handle.close()


class TestPlatformDefault:
    def test_the_platform_defaults_to_the_running_one(self, tmp_path, monkeypatch):
        """Omitting `platform` reads sys.platform rather than assuming either."""
        monkeypatch.setattr(single_instance.sys, "platform", "linux")
        handle = single_instance.acquire(app_dir=tmp_path, flock=lambda fd: None)
        try:
            assert handle is not None
        finally:
            handle.close()

    def test_windows_is_chosen_from_sys_platform(self, tmp_path, monkeypatch):
        monkeypatch.setattr(single_instance.sys, "platform", "win32")
        kernel32 = FakeKernel32(already_exists=False)
        assert (
            single_instance.acquire(app_dir=tmp_path, kernel32=kernel32)
            == kernel32.handle
        )


@pytest.mark.parametrize("platform", ["linux", "darwin", "freebsd"])
def test_every_non_windows_platform_takes_the_posix_path(tmp_path, platform):
    handle = single_instance.acquire(
        app_dir=tmp_path / platform, platform=platform, flock=lambda fd: None
    )
    try:
        assert (tmp_path / platform / single_instance.LOCK_FILENAME).is_file()
    finally:
        handle.close()
