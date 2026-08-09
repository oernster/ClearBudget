"""Save / Save As / Load flows for the database, plus the tray buttons.

Save copies the live database to the remembered save file (prompting to
overwrite when it already exists); the first ever Save behaves as Save As,
prompting for a filename and defaulting to the user's Downloads folder. The
chosen location is persisted between runs (see clear_budget.ui.save_location).
Load replaces the live database from a chosen file, with validation and an
overwrite confirmation when the current database holds data.

Extracted from MainWindow so the window module stays under the LOC limit and
each flow is one readable recipe.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton

from clear_budget.shared.db_validation import validate_db
from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui.save_location import load_save_location, store_save_location
from clear_budget.ui.ui_paths import default_downloads_dir

# Default backup filename offered the first time the user saves.
_DEFAULT_SAVE_NAME = "clearbudget_backup.db"
_DB_FILTER = "Clear Budget Database (*.db)"

# Match the tray's other icon actions (the balance pencil) so the pair reads
# as part of the same control family.
_ICON_BTN_MAX_WIDTH = 32
_ICON_BTN_MAX_HEIGHT = 26


def build_save_load_buttons(read_only: bool) -> tuple[QPushButton, QPushButton]:
    """Return (load_btn, save_btn) for a nav tray, in visual order.

    Both are IconAction-styled so they carry the standard three-state ring.
    Load is disabled for read-only viewers, exactly as the Load menu item is.
    """
    load_btn = QPushButton("📂")
    load_btn.setToolTip("Load database…")
    save_btn = QPushButton("💾")
    save_btn.setToolTip("Save database")
    for btn in (load_btn, save_btn):
        btn.setObjectName(label_roles.ICON_ACTION)
        btn.setMaximumWidth(_ICON_BTN_MAX_WIDTH)
        btn.setMaximumHeight(_ICON_BTN_MAX_HEIGHT)
    load_btn.setEnabled(not read_only)
    return load_btn, save_btn


def _report_saved(parent, dest: Path) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle("Save Successful")
    box.setText(f"Database saved to:\n{dest}")
    label_w = ui_scale.px(460)
    box.setStyleSheet(f"QLabel#qt_msgbox_label {{ min-width: {label_w}px; }}")
    box.exec()


def _copy_and_report(parent, db_path: Path, dest: Path) -> None:
    try:
        shutil.copy2(db_path, dest)
        _report_saved(parent, dest)
    except OSError as exc:
        QMessageBox.critical(parent, "Save Failed", str(exc))


def run_save_flow(parent, db_path: Path) -> None:
    """Save the database to the remembered location, confirming overwrite.

    With no remembered location yet this IS Save As: the user is prompted for
    a filename, defaulting to their Downloads folder.
    """
    target = load_save_location()
    if target is None:
        run_save_as_flow(parent, db_path)
        return
    if target.exists():
        reply = QMessageBox.question(
            parent,
            "Overwrite Save File?",
            f"The save file already exists:\n{target}\n\nOverwrite it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
    _copy_and_report(parent, db_path, target)


def run_save_as_flow(parent, db_path: Path) -> None:
    """Prompt for a save file, remember it, then save the database to it."""
    remembered = load_save_location()
    start = remembered if remembered else default_downloads_dir() / _DEFAULT_SAVE_NAME
    dest, _ = QFileDialog.getSaveFileName(
        parent, "Save Database As", str(start), _DB_FILTER
    )
    if not dest:
        return
    dest_path = Path(dest)
    if dest_path.suffix.lower() != ".db":
        dest_path = dest_path.with_suffix(".db")
    store_save_location(dest_path)
    _copy_and_report(parent, db_path, dest_path)


def _has_existing_data(db_path: Path, conn) -> bool:
    if not db_path.exists():
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bills")
        return cursor.fetchone()[0] > 0
    except Exception:  # noqa: BLE001 (any failure means assume data)
        # Deliberately broad: if the count cannot be read for ANY reason,
        # assume there is data so the user still gets the overwrite
        # confirmation rather than losing it silently.
        return True


def run_load_flow(parent, db_path: Path, conn) -> bool:
    """Replace the live database from a chosen file.

    Returns True when the database was replaced (the caller reloads the UI).
    Starts in the remembered save file's folder when one is set, else the
    user's Downloads folder.
    """
    remembered = load_save_location()
    start_dir = remembered.parent if remembered else default_downloads_dir()
    src, _ = QFileDialog.getOpenFileName(
        parent, "Load Database", str(start_dir), _DB_FILTER
    )
    if not src:
        return False
    src_path = Path(src)
    if src_path.resolve() == db_path.resolve():
        QMessageBox.warning(
            parent,
            "Load",
            "Selected file is the active database - nothing to load.",
        )
        return False

    if _has_existing_data(db_path, conn):
        reply = QMessageBox.question(
            parent,
            "Overwrite Existing Data?",
            "The active database already contains data.\n\n"
            "Loading will permanently replace all bills, income sources, "
            "credit cards, "
            "overrides and settings with the contents of the selected file.\n\n"
            "This cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False

    validation_error = validate_db(src_path)
    if validation_error:
        QMessageBox.critical(
            parent,
            "Invalid Database",
            f"Cannot load - invalid Clear Budget database.\n\n{validation_error}",
        )
        return False

    try:
        shutil.copy2(src_path, db_path)
        return True
    except OSError as exc:
        QMessageBox.critical(parent, "Load Failed", str(exc))
        return False
