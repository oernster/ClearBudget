"""Offering to close a running ClearBudget before its files are replaced.

Telling the user to go and close it themselves leaves them to find the window,
close it and come back to click Retry. Offering to do it is one click, so that
is what is offered.

The consequence is stated plainly, because the close is a forced termination
rather than a request: anything the running session has not saved is lost. The
forced form is deliberate. A close request can be declined; a process that
declines still holds the file lock, so the guarantee the install needs would
not hold. British spelling is used in comments.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from clear_budget.version import APP_NAME

if TYPE_CHECKING:  # pragma: no cover
    from installer.ui.main_window import InstallerMainWindow

TITLE = f"{APP_NAME} is running"
CONFIRM_LABEL = "Close it and continue"
CANCEL_LABEL = "Cancel"
MESSAGE = (
    f"{APP_NAME} is running; its files cannot be replaced while it is "
    "open.\n\n"
    "Close it now and continue? The running session ends immediately, so "
    "anything it has not saved is lost."
)

STILL_RUNNING_TITLE = f"{APP_NAME} could not be closed"


def confirm_close_running_app(window: InstallerMainWindow) -> bool:
    """Ask whether to end the running application. True when the user agrees."""
    box = QMessageBox(window)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(TITLE)
    box.setText(MESSAGE)
    confirm = box.addButton(CONFIRM_LABEL, QMessageBox.AcceptRole)
    box.addButton(CANCEL_LABEL, QMessageBox.RejectRole)
    box.exec()
    return box.clickedButton() is confirm


def report_still_running(window: InstallerMainWindow, message: str) -> None:
    """Say that the application is still running, once closing it has failed."""
    QMessageBox.critical(window, STILL_RUNNING_TITLE, message)
