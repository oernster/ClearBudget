"""The Back Up Everything / Restore Everything flows behind the File menu.

Backup writes one zip of the whole identity-and-data set (accounts plus
every budget; see auth.full_backup). Restore is the destructive mirror:
it replaces EVERY account and every budget, so it is validated first,
double-confirmed in words that name the blast radius and then handed to the
composition root through ``full_restore_requested``, because only main.py
can close the open databases, swap the files and return to the sign-in
screen.
"""

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from clear_budget.auth.full_backup import (
    FullBackupError,
    create_full_backup,
    validate_full_backup,
)
from clear_budget.shared.config import Config
from clear_budget.ui.ui_paths import default_downloads_dir

_BACKUP_TITLE = "Back Up Everything"
_RESTORE_TITLE = "Restore Everything"
_DEFAULT_BACKUP_NAME = "clearbudget_full_backup.zip"
_ZIP_FILTER = "Zip archives (*.zip)"


def backup_everything(window) -> None:
    """Write the full backup to a user-chosen zip and say what went in."""
    dest, _ = QFileDialog.getSaveFileName(
        window,
        _BACKUP_TITLE,
        str(default_downloads_dir() / _DEFAULT_BACKUP_NAME),
        _ZIP_FILTER,
    )
    if not dest:
        return
    try:
        names = create_full_backup(app_dir=Config.app_dir(), dest_path=Path(dest))
    except (FullBackupError, OSError) as exc:
        QMessageBox.warning(window, _BACKUP_TITLE, str(exc))
        return
    budgets = sum(1 for name in names if name.startswith("budget_"))
    QMessageBox.information(
        window,
        _BACKUP_TITLE,
        f"Backed up every account and {budgets} budget database(s) to:\n"
        f"{dest}\n\n"
        "The file is not encrypted, so store it as carefully as the data "
        "itself.",
    )


def restore_everything(window) -> None:
    """Pick, validate and double-confirm a backup, then hand it to main."""
    path, _ = QFileDialog.getOpenFileName(
        window, _RESTORE_TITLE, str(default_downloads_dir()), _ZIP_FILTER
    )
    if not path:
        return
    try:
        validate_full_backup(Path(path))
    except FullBackupError as exc:
        QMessageBox.warning(window, _RESTORE_TITLE, str(exc))
        return
    buttons = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
    cancel = QMessageBox.StandardButton.Cancel
    first = QMessageBox.warning(
        window,
        _RESTORE_TITLE,
        "Restoring replaces EVERY account and every budget on this machine "
        "with the backup's contents.\n\n"
        "The application returns to the sign-in screen afterwards.",
        buttons,
        cancel,
    )
    if first != QMessageBox.StandardButton.Yes:
        return
    second = QMessageBox.warning(
        window,
        _RESTORE_TITLE,
        "This cannot be undone. Replace all accounts and budgets now?",
        buttons,
        cancel,
    )
    if second != QMessageBox.StandardButton.Yes:
        return
    window.full_restore_requested.emit(str(path))
