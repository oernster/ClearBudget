"""An update check whose window has gone before its answer comes back.

main.py destroys the main window while the application keeps running: on Log
Out, on every reload (New Budget, Manage Budgets, a currency change, Load) and
on Restore Everything. The update controller is the window's child, so it goes
with it. A check still out at that moment emitted its answer through the
deleted controller; the worker thread died with "Signal source has been
deleted". Nobody is left to tell, so the answer is dropped; what must not
happen is an exception escaping a thread this application started.

No QApplication is started (see tests/conftest.py) and none is needed: the
defect is the lifetime of a QObject, which a bare QObject parent reproduces.
Deleting that parent takes the controller with it, exactly as the window's
deferred delete does.
"""

from __future__ import annotations

import threading

import shiboken6
from PySide6.QtCore import QObject

from clear_budget.application.services.update_service import (
    UpdateService,
    platform_key_for,
)
from clear_budget.ui.update_check import UpdateCheckController

_CURRENT = "4.2.0"

# Far longer than a check against a stand-in takes, so only a hang reaches it.
_WAIT_SECONDS = 5


class _HeldSource:
    """A release source that answers only once the test lets it."""

    def __init__(self) -> None:
        self.asked = threading.Event()
        self.answer = threading.Event()
        self.worker: threading.Thread | None = None

    def latest_release(self):
        """Say it has been asked, then wait to be allowed to answer."""
        self.worker = threading.current_thread()
        self.asked.set()
        self.answer.wait(_WAIT_SECONDS)
        return None


def test_an_answer_with_nowhere_to_go_is_dropped_not_raised(monkeypatch) -> None:
    escaped: list[BaseException | None] = []
    monkeypatch.setattr(
        threading, "excepthook", lambda raised: escaped.append(raised.exc_value)
    )
    source = _HeldSource()
    window = QObject()
    controller = UpdateCheckController(
        UpdateService(source, _CURRENT, platform_key_for("win32")), window
    )
    controller.check_manually()
    assert source.asked.wait(_WAIT_SECONDS), "the check never started"
    shiboken6.delete(window)
    assert not shiboken6.isValid(controller), "the window kept its controller"
    source.answer.set()
    source.worker.join(_WAIT_SECONDS)
    assert not source.worker.is_alive(), "the check never finished"
    assert escaped == []
