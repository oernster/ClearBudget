"""The second launch's request; the running copy picking it up."""

from __future__ import annotations

from pathlib import Path

from clear_budget.shared import raise_request


class _FakeUser32:
    """Records the foreground permission the Windows branch must grant."""

    def __init__(self) -> None:
        self.allowed: list[int] = []

    def AllowSetForegroundWindow(self, pid: int) -> int:  # noqa: N802 (Win32 name)
        self.allowed.append(pid)
        return 1


class TestRequestRaise:
    def test_it_leaves_a_request_the_running_copy_can_find(self, tmp_path: Path):
        assert raise_request.request_raise(app_dir=tmp_path, platform="linux") is True
        assert (tmp_path / raise_request.REQUEST_FILENAME).exists()

    def test_it_creates_the_data_directory_when_it_is_not_there_yet(
        self, tmp_path: Path
    ):
        app_dir = tmp_path / "not" / "yet"
        assert raise_request.request_raise(app_dir=app_dir, platform="linux") is True
        assert (app_dir / raise_request.REQUEST_FILENAME).exists()

    def test_windows_grants_the_foreground_before_asking(self, tmp_path: Path):
        """Without this the other window flashes in the task bar, never rises."""
        user32 = _FakeUser32()
        assert (
            raise_request.request_raise(
                app_dir=tmp_path, platform="win32", user32=user32
            )
            is True
        )
        assert user32.allowed == [raise_request.ASFW_ANY]

    def test_no_other_platform_touches_the_windows_api(self, tmp_path: Path):
        user32 = _FakeUser32()
        raise_request.request_raise(app_dir=tmp_path, platform="darwin", user32=user32)
        assert user32.allowed == []

    def test_an_unwritable_data_directory_is_not_worth_stopping_for(
        self, tmp_path: Path
    ):
        """The launch is exiting anyway; only the raise is lost."""
        blocked = tmp_path / "a-file"
        blocked.write_text("", encoding="utf-8")
        assert (
            raise_request.request_raise(app_dir=blocked / "under", platform="linux")
            is False
        )


class TestConsumeRaiseRequest:
    def test_it_reports_a_waiting_request(self, tmp_path: Path):
        raise_request.request_raise(app_dir=tmp_path, platform="linux")
        assert raise_request.consume_raise_request(app_dir=tmp_path) is True

    def test_a_request_is_spent_once_read(self, tmp_path: Path):
        """Two launches in a row raise the window once, not twice."""
        raise_request.request_raise(app_dir=tmp_path, platform="linux")
        assert raise_request.consume_raise_request(app_dir=tmp_path) is True
        assert raise_request.consume_raise_request(app_dir=tmp_path) is False

    def test_no_request_is_not_an_error(self, tmp_path: Path):
        assert raise_request.consume_raise_request(app_dir=tmp_path) is False

    def test_an_unreadable_request_is_treated_as_none(self, tmp_path: Path):
        """A directory in its place must not take the running copy down."""
        (tmp_path / raise_request.REQUEST_FILENAME).mkdir()
        assert raise_request.consume_raise_request(app_dir=tmp_path) is False
