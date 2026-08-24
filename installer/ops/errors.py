"""Installer operation errors.

Every failure the setup program reports to the user is one of these, so the UI
can decide what to offer without inspecting exception text. British spelling is
used in comments.
"""

from __future__ import annotations


class InstallerOperationError(RuntimeError):
    pass


class AppRunningError(InstallerOperationError):
    """Raised when ClearBudget is running and the operation needs it closed."""


class AppStillRunningError(AppRunningError):
    """Raised when ClearBudget was asked to close but is still running.

    Distinct from AppRunningError because the offer to close has already been
    taken up: repeating that offer would be pointless, so the UI says what to
    do by hand instead.
    """


class UnsafePayloadEntryError(InstallerOperationError):
    """A payload entry would be written outside the directory it belongs in.

    The payload is produced by this project's own build tooling, so a hostile
    entry is not the expected case. Extraction runs with the user's full
    privileges, though, so the guarantee is enforced rather than assumed.
    """
