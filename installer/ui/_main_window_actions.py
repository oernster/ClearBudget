from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from clear_budget.version import APP_NAME, __version__
from installer.constants import APP_EXE_NAME
from installer.ops.errors import AppStillRunningError
from installer.ops.running_app import close_running_app, launch_app
from installer.state.model import InstalledInfo, InstallerState, Operation
from installer.ui._main_window_buttons import set_buttons_for_allowed_ops
from installer.ui._main_window_ops import (
    LAUNCHABLE_OPS,
    operation_callable,
    target_exe_for,
)
from installer.ui._main_window_types import UiSelections
from installer.ui.close_app_dialog import (
    confirm_close_running_app,
    report_still_running,
)
from installer.ui.licence_dialog import InstallerLicenceDialog

if TYPE_CHECKING:  # pragma: no cover
    from installer.ui.main_window import InstallerMainWindow

# Kept visible long enough for the user to see that something happened.
_COMPLETION_LINGER_MS = 1200
_AUTO_CLOSE_DELAY_MS = 600
# Long enough for the completion message to have been seen before the window
# goes. Derived from the two above rather than written as a third number, so
# shortening the linger cannot leave the close landing before it.
_FINISHED_CLOSE_DELAY_MS = _COMPLETION_LINGER_MS + _AUTO_CLOSE_DELAY_MS


def connect_signals(window: InstallerMainWindow) -> None:
    """Wire every button to its handler.

    Deliberately unguarded. These calls ran inside `except Exception: pass`,
    which could only ever have turned a wiring mistake into a button that
    looks normal and does nothing. A failure here is a programming error and
    should stop the installer at the point it is introduced.
    """
    window._licence_btn.clicked.connect(window._show_installer_licence)
    window._theme_toggle_btn.clicked.connect(window._toggle_theme)
    if getattr(window, "_browse_btn", None) is not None:
        window._browse_btn.clicked.connect(window._browse_install_dir)
    window._btn_primary_left.clicked.connect(
        lambda: window._request_operation(Operation.INSTALL)
    )
    window._btn_primary_right.clicked.connect(
        lambda: window._request_operation(Operation.REPAIR)
    )
    window._btn_uninstall.clicked.connect(
        lambda: window._request_operation(Operation.UNINSTALL)
    )


def show_installer_licence(window: InstallerMainWindow) -> None:
    # Keep a reference so the dialog is not garbage-collected immediately.
    existing = getattr(window, "_installer_licence_dialog", None)
    if isinstance(existing, QDialog):
        try:
            existing.raise_()
            existing.activateWindow()
            return
        except RuntimeError:
            # The remembered dialog's C++ half has already been destroyed, so
            # fall through and build a fresh one.
            pass
    dlg = InstallerLicenceDialog(parent=window)
    window._installer_licence_dialog = dlg

    def _clear_ref() -> None:
        try:
            if getattr(window, "_installer_licence_dialog", None) is dlg:
                window._installer_licence_dialog = None
        except RuntimeError:
            # Window torn down before the dialog finished; the reference it
            # held is going away with it.
            pass

    dlg.finished.connect(_clear_ref)

    # Non-blocking but modal.
    dlg.open()


def default_install_dir() -> Path:
    """The per-user Programs directory, the Windows convention for user apps.

    It was `%LOCALAPPDATA%\\Clear Budget` once, one level too high: program
    files sat beside the app's DATA directory and the setup log, three
    near-identical names at the top of AppData\\Local. Program files belong
    under Programs; an existing install keeps its registered location until
    it is uninstalled, since the maintenance flow reads the registry entry.
    """
    local = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "Programs" / APP_NAME


def browse_install_dir(window: InstallerMainWindow) -> None:
    current = Path(
        window._install_dir_edit.text().strip() or str(default_install_dir())
    )
    chosen = QFileDialog.getExistingDirectory(
        window, "Select installation directory", str(current)
    )
    if chosen:
        window._install_dir_edit.setText(chosen)


def refresh_state(window: InstallerMainWindow) -> None:
    read_entry = getattr(window, "_read_uninstall_entry", None)
    if read_entry is None:
        from installer.state.registry import read_uninstall_entry as read_entry

    entry = read_entry(window._identity.uninstall_key)
    installed = None
    if entry and entry.install_location.exists():
        exe = entry.install_location / "ClearBudget.exe"
        if exe.exists():
            installed = InstalledInfo(
                version=entry.display_version, location=entry.install_location
            )

    state = InstallerState(installer_version=__version__, installed=installed)
    window._state = state

    window._status_line.setText(state.status_line(APP_NAME))

    allowed = state.allowed_operations()
    set_buttons_for_allowed_ops(window, allowed)

    # Set checkboxes to persisted values if available.
    if entry is not None:
        if entry.shortcut_desktop is not None:
            window._desktop_cb.setChecked(entry.shortcut_desktop)
        if entry.shortcut_start_menu is not None:
            window._startmenu_cb.setChecked(entry.shortcut_start_menu)

        # On upgrade/reinstall, default directory to current install dir.
        window._install_dir_edit.setText(str(entry.install_location))


def validate_install_dir(path: Path) -> bool:
    # Best-effort check that the directory is user-writeable.
    try:
        path.mkdir(parents=True, exist_ok=True)
        test = path / ".clearbudget_installer_write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        return True
    except OSError:
        # Not writeable: no permission, a read-only volume, a bad path or a
        # full disk. Every one of those is the same answer to the caller.
        return False


def current_selections(window: InstallerMainWindow) -> UiSelections:
    p = Path(window._install_dir_edit.text().strip() or str(default_install_dir()))
    return UiSelections(
        install_dir=p,
        shortcut_desktop=bool(window._desktop_cb.isChecked()),
        shortcut_start_menu=bool(window._startmenu_cb.isChecked()),
        launch_when_finished=bool(window._launch_cb.isChecked()),
    )


def request_operation(window: InstallerMainWindow, op: Operation) -> None:
    selections = current_selections(window)
    writes_install_dir = op in {
        Operation.INSTALL,
        Operation.UPGRADE,
        Operation.REINSTALL,
    }
    if writes_install_dir and not validate_install_dir(selections.install_dir):
        QMessageBox.critical(
            window,
            "Invalid installation directory",
            "The selected installation directory is not writable without "
            "administrator privileges.",
        )
        return

    if window._op_controller.is_running:
        return

    # Immediately reflect that the operation has begun.
    # This also forces a re-read of the registry after install/uninstall so
    # button states update without requiring a relaunch.
    refresh_state(window)

    window._set_ui_busy(True)
    window._progress.setText("Working...")
    window._progress_bar.setValue(0)

    fn, kwargs = operation_callable(window, op, selections)
    window._debug_last_op = op
    window._debug_last_kwargs = kwargs
    window._op_controller.start(
        fn,
        kwargs=kwargs,
        on_progress=window._on_progress,
        on_finished=lambda r: window._on_operation_finished(op, r),
        on_app_running=lambda msg: window._on_app_running(op, msg),
    )


def on_progress(window: InstallerMainWindow, payload) -> None:
    # payload can be:
    # - str message
    # - {"pct": int, "message": str}
    if isinstance(payload, dict):
        pct = payload.get("pct")
        msg = payload.get("message", "")
        if isinstance(pct, int):
            window._progress_bar.setValue(max(0, min(100, pct)))
        if msg:
            window._progress.setText(str(msg))
        return

    if isinstance(payload, str) and payload:
        window._progress.setText(payload)


def on_app_running(window: InstallerMainWindow, op: Operation, msg: str) -> None:
    """Offer to close the running application, then retry the operation.

    The old behaviour asked the user to go and close it themselves and come
    back to click Retry. Closing it is something the setup program can do, so
    it offers to; it only reports a failure when the process will not end.
    """
    del msg

    window._set_ui_busy(False)
    window._progress.setText("")

    if not confirm_close_running_app(window):
        return

    exe = target_exe_for(window, op, current_selections(window))
    try:
        close_running_app(exe)
    except AppStillRunningError as exc:
        report_still_running(window, str(exc))
        return

    window._request_operation(op)


def on_operation_finished(
    window: InstallerMainWindow,
    op: Operation,
    result,
) -> None:
    window._set_ui_busy(False)
    if result.ok:
        window._progress_bar.setValue(100)
        if op == Operation.UNINSTALL:
            window._progress.setText("Uninstalled")
        else:
            window._progress.setText("Done")
    else:
        if result.message and result.message != "app_running":
            QMessageBox.critical(window, "Operation failed", result.message)
        window._progress.setText("")
        window._progress_bar.setValue(0)

    refresh_state(window)

    # Keep completion visible briefly so users can tell something happened.
    try:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(_COMPLETION_LINGER_MS, lambda: window._progress.setText(""))
    except (ImportError, RuntimeError):
        # Best effort: the label simply keeps its completion text a while
        # longer, which is cosmetic and never a reason to fail here.
        # ImportError if Qt is unavailable, RuntimeError if the label is gone.
        pass

    if result.ok:
        if op in LAUNCHABLE_OPS:
            _launch_if_wanted(window)
        if _should_close_after(window, op):
            _close_shortly(window)
        return


def _should_close_after(window: InstallerMainWindow, op: Operation) -> bool:
    """Whether the setup program should bow out after a successful `op`.

    Every operation that leaves the machine in the state the user asked for
    closes: there is nothing left to do and leaving the window sitting there
    reads as though something is still pending. Install, upgrade, reinstall and
    repair all did exactly that, because the launch branch returned without
    closing and repair fell past the uninstall check entirely.

    Uninstall keeps its existing rule. Launched from Windows Settings it
    closes; if the user opened setup themselves and chose Uninstall, the
    window stays so the result is visible and another operation can follow.
    """
    if op != Operation.UNINSTALL:
        return True
    return bool(getattr(window._cli_args, "uninstall", False))


def _close_shortly(window: InstallerMainWindow) -> None:
    """Close the window once the current work has unwound.

    Deferred rather than immediate, not only so the completion message can
    be read. The operation's worker thread is being retired around this call;
    closing from inside that teardown is how a setup program ends up waiting
    on the thread it is running on.
    """
    try:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(_FINISHED_CLOSE_DELAY_MS, window.close)
    except (ImportError, RuntimeError):
        # Without a timer the close still has to happen, just now rather than
        # after the delay.
        window.close()


def _launch_if_wanted(window: InstallerMainWindow) -> None:
    """Start the freshly installed application when the user asked for it.

    Read from the checkbox rather than from the selections captured when the
    operation started, so the box reflects what is on screen at the moment the
    install completes.
    """
    if not bool(window._launch_cb.isChecked()):
        return
    selections = current_selections(window)
    launch_app(selections.install_dir / APP_EXE_NAME)
