"""Update-check ui: run checks off the ui thread and prompt on the result.

The controller owns the check triggers (a delayed launch check, a daily
re-check while running and the Help menu's manual check) and runs each check
on a worker thread so the one network call can never stall the ui. The result
crosses back to the ui thread through a queued signal to a bound method of
this controller, which lives on the ui thread.

An automatic check that finds a newer release prompts with Download, Skip
This Version and Later; a skipped version is persisted in the app settings
file and never prompts again. Automatic checks are silent on failure and when
up to date; only the manual check reports those outcomes.
"""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from clear_budget.shared.config import Config
from clear_budget.version import APP_NAME

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from clear_budget.application.dto.update_info import UpdateStatus
    from clear_budget.application.services.update_service import UpdateService

__all__ = ["UpdateCheckController", "load_skipped_version", "save_skipped_version"]

# The app settings file also carrying the theme choice.
_SETTINGS_FILE_NAME = "ui_settings.json"
_SKIPPED_KEY = "skipped_update"

# Delay before the automatic launch check, so startup is never contended.
_LAUNCH_CHECK_DELAY_MS = 3000
# One re-check per day while the app stays running.
_CHECK_INTERVAL_HOURS = 24
_MS_PER_HOUR = 60 * 60 * 1000

# Prompt and announcement copy.
_PROMPT_TITLE = "Update available"
_PROMPT_BODY = "{app} {latest} is available.\nYou are running {current}."
_DOWNLOAD_LABEL = "Download"
_SKIP_LABEL = "Skip This Version"
_LATER_LABEL = "Later"
_MANUAL_TITLE = "Check for Updates"
_UP_TO_DATE_BODY = "You are running the latest version."
_UNREACHABLE_BODY = "The update check could not reach GitHub. Please try again later."


def _settings_path():
    return Config.app_dir() / _SETTINGS_FILE_NAME


def load_skipped_version() -> str | None:
    """Return the release version the user chose to skip, if any."""
    try:
        data = json.loads(_settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get(_SKIPPED_KEY) if isinstance(data, dict) else None
    return value if isinstance(value, str) and value else None


def save_skipped_version(version: str) -> None:
    """Persist the release version the user chose to skip."""
    path = _settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data[_SKIPPED_KEY] = version
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        # Persistence is best-effort; the in-session skip still applies.
        pass


class UpdateCheckController(QObject):
    """Runs update checks off the ui thread and prompts on the result."""

    # Emitted from the worker thread; delivery is queued onto the ui thread
    # because the connected slot is a bound method of this ui-thread QObject.
    _result_ready = Signal(object, bool)

    def __init__(self, service: UpdateService, parent: QWidget) -> None:
        super().__init__(parent)
        self._service = service
        self._parent_widget = parent
        self._result_ready.connect(self._on_result)
        QTimer.singleShot(_LAUNCH_CHECK_DELAY_MS, self.check_automatically)
        self._periodic_timer = QTimer(self)
        self._periodic_timer.setInterval(_CHECK_INTERVAL_HOURS * _MS_PER_HOUR)
        self._periodic_timer.timeout.connect(self.check_automatically)
        self._periodic_timer.start()

    def check_automatically(self) -> None:
        """Run a silent check honouring a previously skipped version."""
        self._start(manual=False)

    def check_manually(self) -> None:
        """Run a check that reports every outcome, ignoring any skip."""
        self._start(manual=True)

    def _start(self, manual: bool) -> None:
        skipped = None if manual else load_skipped_version()
        thread = threading.Thread(target=self._run, args=(skipped, manual), daemon=True)
        thread.start()

    def _run(self, skipped: str | None, manual: bool) -> None:
        self._result_ready.emit(self._service.check(skipped), manual)

    def _on_result(self, status: UpdateStatus, manual: bool) -> None:
        if status.update_available:
            _prompt_update(status, self._parent_widget)
        elif manual:
            _announce_no_update(status, self._parent_widget)


def _prompt_update(status: UpdateStatus, parent: QWidget) -> None:
    """Offer Download, Skip This Version and Later for a newer release."""
    box = QMessageBox(parent)
    box.setWindowTitle(_PROMPT_TITLE)
    box.setIcon(QMessageBox.Icon.Information)
    box.setText(
        _PROMPT_BODY.format(app=APP_NAME, latest=status.latest, current=status.current)
    )
    download = box.addButton(_DOWNLOAD_LABEL, QMessageBox.ButtonRole.AcceptRole)
    skip = box.addButton(_SKIP_LABEL, QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(_LATER_LABEL, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(download)
    box.exec()
    clicked = box.clickedButton()
    if clicked is download:
        url = status.download_url or status.page_url
        if url:
            QDesktopServices.openUrl(QUrl(url))
    elif clicked is skip and status.latest:
        save_skipped_version(status.latest)


def _announce_no_update(status: UpdateStatus, parent: QWidget) -> None:
    """Report a manual check that found nothing to offer."""
    body = _UP_TO_DATE_BODY if status.latest is not None else _UNREACHABLE_BODY
    QMessageBox.information(parent, _MANUAL_TITLE, body)
