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
    # The wording claimed it removed user data and cache. It did not; now it
    # deliberately does not: budgets, accounts and the saved theme live in
    # ~/.clearbudget and are left where they are, so a reinstall carries on from
    # where the user left off. Saying so is the point of the dialog.
    box.setText(
        "This will uninstall Clear Budget for the current user.\n\n"
        "Your budgets, accounts and settings are kept, so reinstalling picks up "
        "where you left off. To remove them, delete the .clearbudget folder in "
        "your user folder by hand."
    )
    uninstall_btn = box.addButton("Uninstall", QMessageBox.AcceptRole)
    box.addButton("Cancel", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() == uninstall_btn:
        window._request_operation(Operation.UNINSTALL)
