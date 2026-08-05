"""The two seams every other operation reports through.

The command runner is exercised against real processes, because its whole
purpose is to be the one place a real process is started; the fake stands in
everywhere else. British spelling is used in comments.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from installer.ops.commands import (
    FAILED_RETURNCODE,
    CommandResult,
    SubprocessRunner,
    default_runner,
    powershell_command,
)
from installer.ops.progress import (
    COMPLETE_PCT,
    MESSAGE_KEY,
    MINIMUM_PCT,
    PCT_KEY,
    report,
    scaled,
)
from tests.installer.fakes import RecordingProgress

_SHORT_TIMEOUT_S = 30.0
_HALF = 2


def _python(*code: str) -> list[str]:
    """Return the argument list running a snippet in this interpreter."""
    return [sys.executable, "-c", *code]


class TestCommandResult:
    def test_a_zero_exit_is_success(self) -> None:
        assert CommandResult(0, "out").ok is True

    def test_any_other_exit_is_failure(self) -> None:
        assert CommandResult(FAILED_RETURNCODE, "").ok is False


class TestSubprocessRunner:
    def test_it_runs_a_command_and_captures_its_output(self) -> None:
        result = SubprocessRunner().run(
            _python("print('hello')"), timeout=_SHORT_TIMEOUT_S
        )

        assert result.ok is True
        assert "hello" in result.stdout

    def test_a_non_zero_exit_is_reported_not_raised(self) -> None:
        result = SubprocessRunner().run(
            _python("raise SystemExit(3)"), timeout=_SHORT_TIMEOUT_S
        )

        assert result.ok is False
        assert result.returncode == 3

    def test_a_command_that_cannot_start_is_reported_as_failed(self) -> None:
        result = SubprocessRunner().run(
            ["a-command-that-is-not-installed"], timeout=_SHORT_TIMEOUT_S
        )

        assert result == CommandResult(FAILED_RETURNCODE, "")

    def test_a_command_that_overruns_its_timeout_is_reported_as_failed(self) -> None:
        result = SubprocessRunner().run(
            _python("import time; time.sleep(30)"), timeout=0.2
        )

        assert result.returncode == FAILED_RETURNCODE

    def test_start_detached_starts_a_real_process(self, tmp_path: Path) -> None:
        marker = tmp_path / "started.txt"
        script = f"open(r'{marker}', 'w').write('ok')"

        SubprocessRunner().start_detached(_python(script), cwd=str(tmp_path))

        _wait_for(marker)
        assert marker.read_text(encoding="utf-8") == "ok"

    def test_a_detached_command_that_cannot_start_is_swallowed(self) -> None:
        """Nothing to report to: the caller is on its way out of the process."""
        SubprocessRunner().start_detached(["a-command-that-is-not-installed"])

    def test_the_default_runner_is_the_real_one(self) -> None:
        assert isinstance(default_runner(), SubprocessRunner)


def _wait_for(marker: Path) -> None:
    """Wait briefly for a detached process to write its marker."""
    attempts = 200
    interval_s = 0.05
    for _ in range(attempts):
        if marker.exists():
            return
        time.sleep(interval_s)
    raise AssertionError(f"The detached process never wrote {marker}")


class TestPowershellCommand:
    def test_it_runs_non_interactively_with_no_profile(self) -> None:
        args = powershell_command("Write-Output 1")

        assert args[0].startswith("powershell")
        assert "-NoProfile" in args
        assert "-NonInteractive" in args
        assert args[-1] == "Write-Output 1"

    def test_a_hidden_command_asks_for_no_window(self) -> None:
        assert "Hidden" in powershell_command("x", hidden=True)

    def test_a_visible_command_does_not(self) -> None:
        assert "Hidden" not in powershell_command("x")


class TestReport:
    def test_it_sends_a_percentage_and_a_message(self) -> None:
        progress = RecordingProgress()

        report(progress, COMPLETE_PCT, "Completed")

        assert progress.updates == [{PCT_KEY: COMPLETE_PCT, MESSAGE_KEY: "Completed"}]

    def test_no_reporter_is_not_an_error(self) -> None:
        report(None, COMPLETE_PCT, "Completed")


class TestScaled:
    def test_the_start_of_a_phase_reports_its_start(self) -> None:
        assert scaled(0, 10, MINIMUM_PCT, COMPLETE_PCT) == MINIMUM_PCT

    def test_the_end_of_a_phase_reports_its_end(self) -> None:
        assert scaled(10, 10, MINIMUM_PCT, COMPLETE_PCT) == COMPLETE_PCT

    def test_it_interpolates_across_the_span(self) -> None:
        assert scaled(5, 10, MINIMUM_PCT, COMPLETE_PCT) == COMPLETE_PCT // _HALF

    @pytest.mark.parametrize("total", [0, -1])
    def test_nothing_to_do_reports_the_phase_complete(self, total: int) -> None:
        """A bundle of zero bytes must not divide by zero, nor stall the bar."""
        assert scaled(0, total, MINIMUM_PCT, COMPLETE_PCT) == COMPLETE_PCT
