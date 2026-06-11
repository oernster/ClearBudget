from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

from installer.state.model import Operation

if TYPE_CHECKING:  # pragma: no cover
    from installer.ui.main_window import InstallerMainWindow


def confirm_and_run_uninstall(window: InstallerMainWindow) -> None:
    box = QMessageBox(window)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("Confirm uninstall")
    box.setText(
        "This will uninstall Clear Budget for the current user and remove user data "
        "and cache."
    )
    uninstall_btn = box.addButton("Uninstall", QMessageBox.AcceptRole)
    box.addButton("Cancel", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() == uninstall_btn:
        window._request_operation(Operation.UNINSTALL)
