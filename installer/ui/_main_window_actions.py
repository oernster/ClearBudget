from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from installer.ops.errors import InstallerOperationError
from installer.ops.install_ops import InstallOptions, install_new, upgrade_or_reinstall
from installer.ops.repair_ops import RepairOptions, repair
from installer.ops.uninstall_ops import UninstallOptions, uninstall_with_feedback
from installer.state.model import InstalledInfo, InstallerState, Operation
from installer.ui.licence_dialog import InstallerLicenceDialog
from clear_budget.version import APP_NAME, __version__

from installer.ui._main_window_types import UiSelections

if TYPE_CHECKING:  # pragma: no cover
    from installer.ui.main_window import InstallerMainWindow


def connect_signals(window: InstallerMainWindow) -> None:
    try:
        window._licence_btn.clicked.connect(window._show_installer_licence)
    except Exception:
        pass
    try:
        window._theme_toggle_btn.clicked.connect(window._toggle_theme)
    except Exception:
        pass
    try:
        if getattr(window, "_browse_btn", None) is not None:
            window._browse_btn.clicked.connect(window._browse_install_dir)
    except Exception:
        pass
    try:
        window._btn_primary_left.clicked.connect(
            lambda: window._request_operation(Operation.INSTALL)
        )
    except Exception:
        pass
    try:
        window._btn_primary_right.clicked.connect(
            lambda: window._request_operation(Operation.REPAIR)
        )
    except Exception:
        pass
    try:
        window._btn_uninstall.clicked.connect(
            lambda: window._request_operation(Operation.UNINSTALL)
        )
    except Exception:
        pass


def show_installer_licence(window: InstallerMainWindow) -> None:
    # Keep a reference so the dialog is not garbage-collected immediately.
    existing = getattr(window, "_installer_licence_dialog", None)
    if isinstance(existing, QDialog):
        try:
            existing.raise_()
            existing.activateWindow()
            return
        except Exception:
            pass
    dlg = InstallerLicenceDialog(parent=window)
    window._installer_licence_dialog = dlg

    def _clear_ref() -> None:
        try:
            if getattr(window, "_installer_licence_dialog", None) is dlg:
                window._installer_licence_dialog = None
        except Exception:
            pass

    try:
        dlg.finished.connect(_clear_ref)
    except Exception:
        pass

    # Non-blocking but modal.
    dlg.open()


def default_install_dir() -> Path:
    local = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / APP_NAME


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


def set_buttons_for_allowed_ops(
    window: InstallerMainWindow,
    allowed: set[Operation] | frozenset[Operation],
) -> None:
    # Primary buttons are shown in the center row. We use up to two.
    # Uninstall is shown separately in red.
    window._btn_uninstall.setVisible(Operation.UNINSTALL in allowed)

    primary_ops: list[Operation] = [
        op
        for op in [
            Operation.INSTALL,
            Operation.UPGRADE,
            Operation.REINSTALL,
            Operation.REPAIR,
        ]
        if op in allowed
    ]
    left = primary_ops[0] if primary_ops else None
    right = primary_ops[1] if len(primary_ops) > 1 else None

    def _label(op: Operation) -> str:
        return {
            Operation.INSTALL: "Install",
            Operation.UPGRADE: "Upgrade",
            Operation.REINSTALL: "Reinstall",
            Operation.REPAIR: "Repair",
        }[op]

    if left is None:
        window._btn_primary_left.setVisible(False)
    else:
        window._btn_primary_left.setVisible(True)
        window._btn_primary_left.setText(_label(left))
        try:
            window._btn_primary_left.clicked.disconnect()
        except Exception:
            pass
        window._btn_primary_left.clicked.connect(
            lambda: window._request_operation(left)
        )

    if right is None:
        window._btn_primary_right.setVisible(False)
    else:
        window._btn_primary_right.setVisible(True)
        window._btn_primary_right.setText(_label(right))
        try:
            window._btn_primary_right.clicked.disconnect()
        except Exception:
            pass
        window._btn_primary_right.clicked.connect(
            lambda: window._request_operation(right)
        )


def validate_install_dir(path: Path) -> bool:
    # Best-effort check that the directory is user-writeable.
    try:
        path.mkdir(parents=True, exist_ok=True)
        test = path / ".clearbudget_installer_write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def current_selections(window: InstallerMainWindow) -> UiSelections:
    p = Path(window._install_dir_edit.text().strip() or str(default_install_dir()))
    return UiSelections(
        install_dir=p,
        shortcut_desktop=bool(window._desktop_cb.isChecked()),
        shortcut_start_menu=bool(window._startmenu_cb.isChecked()),
    )


def request_operation(window: InstallerMainWindow, op: Operation) -> None:
    selections = current_selections(window)
    if op in {Operation.INSTALL, Operation.UPGRADE, Operation.REINSTALL}:
        if not validate_install_dir(selections.install_dir):
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


def on_progress(window: InstallerMainWindow, payload) -> None:  # noqa: ANN001
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


def set_ui_busy(window: InstallerMainWindow, busy: bool) -> None:
    window._progress_bar.setVisible(busy)
    for w in [
        window._btn_primary_left,
        window._btn_primary_right,
        window._btn_uninstall,
        window._licence_btn,
        window._theme_toggle_btn,
        window._install_dir_edit,
        window._desktop_cb,
        window._startmenu_cb,
    ]:
        w.setEnabled(not busy)


def on_app_running(window: InstallerMainWindow, op: Operation, msg: str) -> None:
    del msg

    window._set_ui_busy(False)
    window._progress.setText("")
    box = QMessageBox(window)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(f"{APP_NAME} is running")
    box.setText(f"Please close {APP_NAME} and click Retry.")
    retry = box.addButton("Retry", QMessageBox.AcceptRole)
    box.addButton("Cancel", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() == retry:
        window._request_operation(op)


def on_operation_finished(
    window: InstallerMainWindow,
    op: Operation,
    result,
) -> None:  # noqa: ANN001
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

        QTimer.singleShot(1200, lambda: window._progress.setText(""))
    except Exception:
        pass

    if op == Operation.UNINSTALL and result.ok:
        # Only auto-close when we were explicitly launched as an uninstaller
        # (e.g. from Windows Settings via UninstallString).
        if getattr(window._cli_args, "uninstall", False):
            try:
                from PySide6.QtCore import QTimer

                QTimer.singleShot(600, window.close)
            except Exception:
                window.close()
        return


def operation_callable(
    window: InstallerMainWindow,
    op: Operation,
    selections: UiSelections,
):
    read_entry = getattr(window, "_read_uninstall_entry", None)
    if read_entry is None:
        from installer.state.registry import read_uninstall_entry as read_entry

    entry = read_entry(window._identity.uninstall_key)
    current_install_dir = entry.install_location if entry else None

    if op == Operation.INSTALL:
        return (
            install_new,
            {
                "identity": window._identity,
                "opts": InstallOptions(
                    target_dir=selections.install_dir,
                    create_desktop_shortcut=selections.shortcut_desktop,
                    create_start_menu_shortcut=selections.shortcut_start_menu,
                ),
            },
        )

    if op in {Operation.UPGRADE, Operation.REINSTALL}:
        if current_install_dir is None:
            raise InstallerOperationError("No existing installation detected")
        return (
            upgrade_or_reinstall,
            {
                "identity": window._identity,
                "current_install_dir": current_install_dir,
                "opts": InstallOptions(
                    target_dir=selections.install_dir,
                    create_desktop_shortcut=selections.shortcut_desktop,
                    create_start_menu_shortcut=selections.shortcut_start_menu,
                ),
            },
        )

    if op == Operation.REPAIR:
        return (
            repair,
            {
                "identity": window._identity,
                "opts": RepairOptions(
                    restore_desktop_shortcut=selections.shortcut_desktop,
                    restore_start_menu_shortcut=selections.shortcut_start_menu,
                ),
            },
        )

    if op == Operation.UNINSTALL:
        return (
            uninstall_with_feedback,
            {
                "identity": window._identity,
                "opts": UninstallOptions(remove_user_data=True),
            },
        )

    raise InstallerOperationError(f"Unsupported operation: {op}")

