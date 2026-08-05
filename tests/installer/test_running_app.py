"""Detecting the running application, closing it and launching it again.

Every process query and every kill goes through the injectable controller, so
nothing here lists or ends a real process. The one real thing exercised is the
matching itself, against hand-written process entries shaped exactly as psutil
presents them. British spelling is used in comments.
"""

from __future__ import annotations

from pathlib import Path

import psutil
import pytest

from installer.constants import APP_EXE_NAME
from installer.ops.errors import AppStillRunningError
from installer.ops.running_app import (
    CLOSE_POLL_ATTEMPTS,
    PsutilProcessController,
    close_running_app,
    default_controller,
    default_process_iter,
    is_app_running,
    launch_app,
)
from tests.installer.fakes import (
    FakeProcess,
    FakeProcessController,
    FakeRunner,
    RaisingProcess,
)

_PID = 4321
_OTHER_PID = 8765


@pytest.fixture()
def exe(tmp_path: Path) -> Path:
    """Return a path standing in for the installed executable."""
    path = tmp_path / APP_EXE_NAME
    path.write_bytes(b"exe")
    return path


def _sleeps() -> tuple[list[float], object]:
    """Return a recorder and the sleeper that feeds it, so no test waits."""
    recorded: list[float] = []
    return recorded, recorded.append


class TestMatchingProcesses:
    """The real controller, against a process list under the test's control."""

    def _controller(self, *processes: object) -> PsutilProcessController:
        return PsutilProcessController(iter_processes=lambda: list(processes))

    def test_a_process_running_the_executable_is_found(self, exe: Path) -> None:
        controller = self._controller(FakeProcess(pid=_PID, exe=str(exe)))

        assert controller.running_pids(exe) == (_PID,)

    def test_every_matching_process_is_found_not_only_the_first(
        self, exe: Path
    ) -> None:
        controller = self._controller(
            FakeProcess(pid=_PID, exe=str(exe)),
            FakeProcess(pid=_OTHER_PID, exe=str(exe)),
        )

        assert controller.running_pids(exe) == (_PID, _OTHER_PID)

    def test_another_executable_of_the_same_name_elsewhere_is_not_matched(
        self, exe: Path, tmp_path: Path
    ) -> None:
        """Matching is on the resolved path, so a copy elsewhere is left alone."""
        elsewhere = tmp_path / "other" / APP_EXE_NAME
        elsewhere.parent.mkdir()
        elsewhere.write_bytes(b"exe")
        controller = self._controller(FakeProcess(pid=_PID, exe=str(elsewhere)))

        assert controller.running_pids(exe) == ()

    def test_a_process_with_no_readable_executable_is_skipped(self, exe: Path) -> None:
        controller = self._controller(FakeProcess(pid=_PID, exe=None))

        assert controller.running_pids(exe) == ()

    @pytest.mark.parametrize(
        "error",
        [
            psutil.NoSuchProcess(_PID),
            psutil.AccessDenied(_PID),
            OSError("gone"),
            TypeError("odd"),
        ],
    )
    def test_a_process_that_cannot_be_inspected_is_skipped(
        self, exe: Path, error: BaseException
    ) -> None:
        controller = self._controller(RaisingProcess(error))

        assert controller.running_pids(exe) == ()

    def test_a_process_with_an_unusable_id_is_skipped(self, exe: Path) -> None:
        controller = self._controller(FakeProcess(pid="not a pid", exe=str(exe)))

        assert controller.running_pids(exe) == ()

    def test_the_live_process_list_is_readable(self) -> None:
        """The one call that touches the real machine; only to read it."""
        assert list(default_process_iter()) != []

    def test_the_default_controller_is_the_real_one(self) -> None:
        assert isinstance(default_controller(), PsutilProcessController)


class TestKilling:
    def test_it_ends_the_process_it_is_given(self) -> None:
        ended: list[int] = []
        controller = PsutilProcessController(kill_process=ended.append)

        controller.kill(_PID)

        assert ended == [_PID]

    @pytest.mark.parametrize(
        "error", [psutil.NoSuchProcess(_PID), psutil.AccessDenied(_PID), OSError("no")]
    )
    def test_a_process_that_has_already_gone_is_not_an_error(
        self, error: BaseException
    ) -> None:
        def _raise(pid: int) -> None:
            raise error

        PsutilProcessController(kill_process=_raise).kill(_PID)


class TestIsAppRunning:
    def test_it_is_true_while_a_process_holds_the_executable(self, exe: Path) -> None:
        assert is_app_running(exe, FakeProcessController(exe, [_PID])) is True

    def test_it_is_false_when_nothing_matches(self, exe: Path) -> None:
        assert is_app_running(exe, FakeProcessController(exe)) is False


class TestCloseRunningApp:
    def test_it_ends_every_matching_process(self, exe: Path) -> None:
        controller = FakeProcessController(exe, [_PID, _OTHER_PID])
        _recorded, sleeper = _sleeps()

        close_running_app(exe, controller, sleep=sleeper)

        assert controller.killed == [_PID, _OTHER_PID]

    def test_it_returns_at_once_when_nothing_was_running(self, exe: Path) -> None:
        controller = FakeProcessController(exe)
        recorded, sleeper = _sleeps()

        close_running_app(exe, controller, sleep=sleeper)

        assert controller.killed == []
        assert recorded == []

    def test_it_waits_for_the_file_lock_to_release(self, exe: Path) -> None:
        """The process is ended, then polled for until it actually goes."""
        controller = FakeProcessController(exe, [_PID], vanish_after=3)
        recorded, sleeper = _sleeps()

        close_running_app(exe, controller, sleep=sleeper)

        assert recorded != []
        assert len(recorded) < CLOSE_POLL_ATTEMPTS

    def test_a_process_that_will_not_end_is_reported(self, exe: Path) -> None:
        controller = FakeProcessController(
            exe, [_PID], vanish_after=CLOSE_POLL_ATTEMPTS * 2
        )
        recorded, sleeper = _sleeps()

        with pytest.raises(AppStillRunningError):
            close_running_app(exe, controller, sleep=sleeper)

        assert len(recorded) == CLOSE_POLL_ATTEMPTS

    def test_a_process_that_goes_on_the_very_last_check_still_counts(
        self, exe: Path
    ) -> None:
        """The final wait is followed by one more look, so a late exit passes."""
        controller = FakeProcessController(
            exe, [_PID], vanish_after=CLOSE_POLL_ATTEMPTS + 1
        )
        _recorded, sleeper = _sleeps()

        close_running_app(exe, controller, sleep=sleeper)

    def test_the_wait_is_bounded_rather_than_indefinite(self, exe: Path) -> None:
        """A stuck process must not hang the setup program for ever."""
        controller = FakeProcessController(
            exe, [_PID], vanish_after=CLOSE_POLL_ATTEMPTS * 2
        )
        recorded, sleeper = _sleeps()

        with pytest.raises(AppStillRunningError):
            close_running_app(exe, controller, sleep=sleeper)

        assert sum(recorded) == pytest.approx(CLOSE_POLL_ATTEMPTS * 0.1)


class TestLaunchApp:
    def test_it_starts_the_application_detached_in_its_own_directory(
        self, exe: Path
    ) -> None:
        runner = FakeRunner()

        launch_app(exe, runner)

        assert runner.detached == [([str(exe)], str(exe.parent))]
