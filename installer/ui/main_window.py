"""Main installer window (Stellody-like UI)."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMainWindow, QMessageBox

from installer.constants import InstallerIdentity
from installer.state.registry import read_uninstall_entry
from installer.state.model import Operation
from installer.ui.themes import DARK, LIGHT, Theme
from installer.ui.worker import OperationController, OperationResult
from installer.ui.icons import build_installer_window_icon
from installer.ui._main_window_build import build_installer_main_window_ui
from installer.ui._main_window_actions import (
    browse_install_dir,
    connect_signals,
    on_app_running,
    on_operation_finished,
    on_progress,
    refresh_state,
    request_operation,
    set_buttons_for_allowed_ops,
    set_ui_busy,
    show_installer_licence,
)
from installer.ui._main_window_uninstall import confirm_and_run_uninstall
from installer.ui._main_window_types import UiSelections
from installer.ui._header_fit import HeaderFitController

from clear_budget.shared.resources import find_qt_window_icon_path
from clear_budget.version import APP_NAME

# Backwards-compat for tests that monkeypatch
# `installer.ui.main_window.read_uninstall_entry`.
# Actual runtime uses `self._read_uninstall_entry`.
read_uninstall_entry = read_uninstall_entry


class InstallerMainWindow(QMainWindow):
    operationRequested = Signal(str, object)

    def __init__(self, cli_args) -> None:  # noqa: ANN001 (Qt entrypoint)
        super().__init__()

        if os.name != "nt":
            raise RuntimeError("Installer UI is Windows-only")

        self._cli_args = cli_args
        self._identity = InstallerIdentity()
        self._op_controller = OperationController()
        self._read_uninstall_entry = read_uninstall_entry

        # Default to dark mode (per UX requirement).
        self._theme: Theme = DARK

        self.setWindowTitle(f"{APP_NAME} Setup")

        # Size policy
        # -----------
        # The installer used to be fixed-size. That can cause text clipping under
        # Windows DPI scaling / Accessibility text size / mixed-DPI multi-monitor
        # setups (see [`crapinstaller.png`](crapinstaller.png:1)).
        #
        # Use a minimum size for the intended design, but allow width/height to
        # grow if required to keep all header text visible.
        self.setMinimumSize(750, 520)
        self.resize(750, 520)

        self._header_fit = HeaderFitController(self)

        # Window icon (taskbar/titlebar). This is separate from the exe icon.
        try:
            from PySide6.QtGui import QIcon

            icon = build_installer_window_icon(
                project_root=Path(__file__).resolve().parents[2]
            )
            if not icon.isNull():
                self.setWindowIcon(icon)
            else:
                icon_path = find_qt_window_icon_path(
                    project_root=Path(__file__).resolve().parents[2]
                )
                if icon_path is not None:
                    self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass

        build_installer_main_window_ui(self)
        # Ensure header fitting sees the post-build widgets before any early
        # Qt events (some platforms deliver events during/after widget creation).
        self._header_fit.ensure_now()
        self._connect_signals()
        self._apply_theme()
        self._refresh_state()

        # Defer sizing pass until Qt has performed initial layout.
        self._header_fit.schedule()

        # If invoked as uninstaller from Settings.
        if getattr(cli_args, "uninstall", False):
            self._confirm_and_run_uninstall()

    def _connect_signals(self) -> None:
        connect_signals(self)

    def _apply_theme(self) -> None:
        self.setStyleSheet(self._theme.qss)
        self._theme_toggle_btn.setText(self._theme.toggle_label)
        self._header_fit.on_theme_applied()
        self._header_fit.schedule()

    def _toggle_theme(self) -> None:
        self._theme = DARK if self._theme is LIGHT else LIGHT
        self._apply_theme()

    def showEvent(self, event) -> None:  # noqa: ANN001 (Qt override)
        super().showEvent(event)
        self._header_fit.schedule()

    def resizeEvent(self, event) -> None:  # noqa: ANN001 (Qt override)
        super().resizeEvent(event)
        self._header_fit.schedule()

    def event(self, event) -> bool:  # noqa: ANN001 (Qt override)
        header_fit = getattr(self, "_header_fit", None)
        if header_fit is not None and header_fit.should_watch_event_type(event.type()):
            header_fit.schedule()
        return super().event(event)

    def _show_installer_licence(self) -> None:
        show_installer_licence(self)

    def _default_install_dir(self) -> Path:
        # Kept for backwards-compat with any external calls.
        from installer.ui._main_window_actions import default_install_dir

        return default_install_dir()

    def _browse_install_dir(self) -> None:
        browse_install_dir(self)

    def _refresh_state(self) -> None:
        refresh_state(self)

    def _set_buttons_for_allowed_ops(
        self, allowed: set[Operation] | frozenset[Operation]
    ) -> None:
        set_buttons_for_allowed_ops(self, allowed)

    def _validate_install_dir(self, path: Path) -> bool:
        from installer.ui._main_window_actions import validate_install_dir

        return validate_install_dir(path)

    def _current_selections(self) -> UiSelections:
        from installer.ui._main_window_actions import current_selections

        return current_selections(self)

    def _request_operation(self, op: Operation) -> None:
        request_operation(self, op)

    def _on_progress(self, payload) -> None:  # noqa: ANN001
        on_progress(self, payload)

    def closeEvent(self, event) -> None:  # noqa: ANN001 (Qt override)
        if self._op_controller.is_running:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Operation in progress")
            box.setText("An operation is running. Do you want to cancel and exit?")
            cancel_exit = box.addButton("Cancel && Exit", QMessageBox.AcceptRole)
            box.addButton("Keep running", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() == cancel_exit:
                self._progress.setText("Cancelling...")
                self._op_controller.force_stop(timeout_ms=1500)
                event.accept()
                return
            event.ignore()
            return
        event.accept()

    def _set_ui_busy(self, busy: bool) -> None:
        set_ui_busy(self, busy)

    def _on_app_running(self, op: Operation, msg: str) -> None:
        on_app_running(self, op, msg)

    def _on_operation_finished(self, op: Operation, result: OperationResult) -> None:
        on_operation_finished(self, op, result)

    def _operation_callable(self, op: Operation, selections: UiSelections):
        from installer.ui._main_window_actions import operation_callable

        return operation_callable(self, op, selections)

    # Synchronous runner removed: operations run in background via OperationController.

    def _confirm_and_run_uninstall(self) -> None:
        confirm_and_run_uninstall(self)

