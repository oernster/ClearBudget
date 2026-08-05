"""Hand-written test doubles for the installer's external seams.

No mocking library is used anywhere in this suite. The setup program reaches
outside itself through exactly three seams, so three small recording doubles
cover the lot: a CommandRunner for anything shelled out, a ProcessController
for anything listed or ended, a progress reporter for what the bar is told.

British spelling is used in comments.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from installer.ops.commands import CommandResult
from installer.ops.progress import MESSAGE_KEY, PCT_KEY


class FakeRunner:
    """Records every command it is given and replays scripted results."""

    def __init__(
        self,
        results: Sequence[CommandResult] | None = None,
        default: CommandResult | None = None,
    ) -> None:
        self.calls: list[tuple[list[str], float]] = []
        self.detached: list[tuple[list[str], str | None]] = []
        self._results = list(results or ())
        self._default = default if default is not None else CommandResult(0, "")

    def run(self, args: Sequence[str], *, timeout: float) -> CommandResult:
        """Record the command and return the next scripted result."""
        self.calls.append((list(args), timeout))
        if self._results:
            return self._results.pop(0)
        return self._default

    def start_detached(self, args: Sequence[str], *, cwd: str | None = None) -> None:
        """Record a detached start."""
        self.detached.append((list(args), cwd))

    @property
    def commands(self) -> list[list[str]]:
        """Return just the argument lists of the commands that were run."""
        return [args for args, _ in self.calls]


class FakeProcessController:
    """A process list under the test's control, plus the kills made against it.

    ``vanish_after`` is how many queries the processes survive: zero means they
    are gone as soon as they are ended; a large number means they never go,
    which is what a process refusing to close looks like.
    """

    def __init__(
        self,
        exe_path: Path | None = None,
        pids: Sequence[int] = (),
        *,
        vanish_after: int = 0,
    ) -> None:
        self.exe_path = exe_path
        self.pids = list(pids)
        self.killed: list[int] = []
        self.queries = 0
        self._vanish_after = vanish_after

    def running_pids(self, exe_path: Path) -> tuple[int, ...]:
        """Return the scripted pids, for the executable this fake stands for."""
        self.queries += 1
        if self.exe_path is not None and Path(exe_path) != self.exe_path:
            return ()
        if self.killed and self.queries > self._vanish_after:
            return ()
        return tuple(self.pids)

    def kill(self, pid: int) -> None:
        """Record that a process was ended."""
        self.killed.append(pid)


class FakeProcess:
    """One entry in a process list, shaped as psutil presents it."""

    def __init__(self, pid: object = 0, exe: object = None) -> None:
        self.info = {"pid": pid, "exe": exe}


class RaisingProcess:
    """A process list entry that raises when its details are read."""

    def __init__(self, error: BaseException) -> None:
        self._error = error

    @property
    def info(self) -> dict[str, object]:
        """Raise the scripted error, as a process that has gone would."""
        raise self._error


class RecordingProgress:
    """Collects the progress updates an operation reports."""

    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def __call__(self, payload: dict[str, object] | str) -> None:
        """Record one update, which every operation sends as a mapping."""
        self.updates.append(dict(payload) if isinstance(payload, dict) else {})

    @property
    def percentages(self) -> list[int]:
        """Return the reported percentages in order."""
        return [int(update[PCT_KEY]) for update in self.updates]

    @property
    def messages(self) -> list[str]:
        """Return the reported phase messages in order."""
        return [str(update[MESSAGE_KEY]) for update in self.updates]


class CancelledEvent:
    """A cancel flag that is already set."""

    def is_set(self) -> bool:
        """Report that the user has asked to stop."""
        return True


class LiveEvent:
    """A cancel flag that is never set."""

    def is_set(self) -> bool:
        """Report that the user has not asked to stop."""
        return False


class CountdownEvent:
    """A cancel flag that trips after a set number of checks."""

    def __init__(self, trips_after: int) -> None:
        self.checks = 0
        self._trips_after = trips_after

    def is_set(self) -> bool:
        """Report not cancelled until the countdown runs out."""
        self.checks += 1
        return self.checks > self._trips_after
