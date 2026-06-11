"""Shared "import viewer package" flow - used by LoginDialog and the Users menu."""

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget

from clear_budget.auth.models import User
from clear_budget.auth.user_store import UserStore
from clear_budget.auth.viewer_package import import_viewer_package, UsernameClashError


def run_import_viewer_package_flow(
    parent: QWidget, user_store: UserStore
) -> User | None:
    """Run the file picker + username-clash resolution + import.

    Returns the imported/refreshed User, or None if the user cancelled or
    the import failed (an error dialog is shown in the failure case).
    """
    src, _ = QFileDialog.getOpenFileName(
        parent,
        "Import Viewer Package",
        str(Path.home()),
        "ClearBudget Viewer Package (*.zip)",
    )
    if not src:
        return None

    username_override: str | None = None
    refresh = False
    while True:
        try:
            return import_viewer_package(
                Path(src),
                user_store,
                username_override=username_override,
                refresh=refresh,
            )
        except UsernameClashError as exc:
            refresh = False
            if exc.existing_is_viewer:
                box = QMessageBox(parent)
                box.setIcon(QMessageBox.Icon.Question)
                box.setWindowTitle("Username Already In Use")
                box.setText(
                    f"A viewer account '{exc.username}' is already installed "
                    "on this machine.\n\n"
                    "Refresh it with this package's data, or choose a "
                    "different username for a new account?"
                )
                refresh_btn = box.addButton(
                    "Refresh", QMessageBox.ButtonRole.AcceptRole
                )
                choose_btn = box.addButton(
                    "Choose New Username", QMessageBox.ButtonRole.ActionRole
                )
                box.addButton(QMessageBox.StandardButton.Cancel)
                box.setDefaultButton(refresh_btn)
                box.exec()
                clicked = box.clickedButton()
                if clicked is refresh_btn:
                    refresh = True
                    username_override = None
                    continue
                if clicked is not choose_btn:
                    return None
                # else fall through to choose a new username below

            new_username, ok = QInputDialog.getText(
                parent,
                "Choose a Username",
                f"The username '{exc.username}' is already in use on this "
                "machine.\n\nChoose a different username for this account.\n"
                "You can export your full database later if you want to "
                "share an exact copy with someone else.",
            )
            if not ok or not new_username.strip():
                return None
            username_override = new_username.strip()
        except (ValueError, OSError) as exc:
            QMessageBox.critical(parent, "Import Failed", str(exc))
            return None
