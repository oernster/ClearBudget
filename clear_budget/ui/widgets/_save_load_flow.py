"""Save / Save As / Load flows for the database, plus the tray buttons.

Save snapshots the live database to the remembered save file (prompting to
overwrite when it already exists); the first ever Save behaves as Save As,
prompting for a filename and defaulting to the user's Downloads folder. The
chosen location is persisted between runs (see clear_budget.ui.save_location).
The snapshot goes through SQLite's backup API rather than a file copy,
because the database is open and a byte copy of one mid-transaction is a
copy of a state that never existed.

Load only CHOOSES and validates. It hands the path back and the composition
root does the replacing, because the live database has to be closed first
and only `main.py` owns its lifetime. See clear_budget.shared.db_copy.

Extracted from MainWindow so the window module stays under the LOC limit and
each flow is one readable recipe.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QFrame, QMessageBox, QPushButton

from clear_budget.shared.db_copy import DatabaseCopyError, backup_open_database
from clear_budget.shared.db_validation import validate_db
from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui.save_location import load_save_location, store_save_location
from clear_budget.ui.ui_paths import default_downloads_dir

# One source for the icon-button chrome, shared with the theme toggle.
from clear_budget.ui.utils.format_helpers import NAV_ICON_BTN_CHROME_PX

# Default backup filename offered the first time the user saves.
_DEFAULT_SAVE_NAME = "clearbudget_backup.db"
_DB_FILTER = "ClearBudget Database (*.db)"


def _tray_icon_button(glyph: str, tooltip: str, glyph_height: int) -> QPushButton:
    """One emoji icon button for the nav tray's far-left group.

    IconAction-styled so it carries the standard three-state ring. The glyph
    is measured and scaled to paint at `glyph_height`, the same height the
    tray's app-icon button is scaled to, so the group reads as one matched
    family. The font goes on as a widget-level stylesheet WITH a selector,
    for the same reasons as the theme toggle: a stylesheet rule beats setFont
    and a bare font-size would cascade to the tooltip. The size is fixed to
    the glyph plus the ring chrome, because Qt's default push-button minimum
    would otherwise make an icon-sized control 80-odd pixels wide.
    """
    from clear_budget.ui.utils.glyph_metrics import glyph_font_px_for_height

    btn = QPushButton(glyph)
    btn.setToolTip(tooltip)
    btn.setObjectName(label_roles.ICON_ACTION)
    glyph_px = glyph_font_px_for_height(glyph, glyph_height)
    btn.setStyleSheet(f"QPushButton#IconAction {{ font-size: {glyph_px}px; }}")
    side = glyph_height + NAV_ICON_BTN_CHROME_PX
    btn.setFixedSize(side, side)
    return btn


def build_save_load_buttons(
    read_only: bool, glyph_height: int
) -> tuple[QPushButton, QPushButton]:
    """Return (load_btn, save_btn) for a nav tray, in visual order.

    Load is disabled for read-only viewers, exactly as the Load menu item is.
    """
    load_btn = _tray_icon_button("📂", "Load database…", glyph_height)
    save_btn = _tray_icon_button("💾", "Save database", glyph_height)
    load_btn.setEnabled(not read_only)
    return load_btn, save_btn


def build_budgets_button(read_only: bool, glyph_height: int) -> QPushButton:
    """Return the switch-budget button for a nav tray.

    Sits with load and save, left of the separator, because it acts on the
    application rather than deciding which page is being looked at. Disabled
    for read-only viewers: a viewer's database arrives from an imported
    package and that account owns exactly the one budget.
    """
    btn = _tray_icon_button("🔄", "Switch budget…", glyph_height)
    btn.setEnabled(not read_only)
    return btn


def build_settings_bank_buttons(
    read_only: bool, glyph_height: int
) -> tuple[QFrame, QPushButton, QPushButton]:
    """Return (separator, settings_btn, bank_btn) for a nav tray.

    The separator is a themed vertical rule, returned here but placed by the
    caller AFTER both buttons: it divides the four controls that act on the
    application (load, save, Preferences, Bank Account) from the four tabs
    that follow them, which only decide which page you are looking at. It used
    to sit between load/save and the settings pair, back when the tabs were
    a strip of their own and there was nothing else in the tray to divide
    them from. Both buttons are disabled for read-only
    viewers, exactly as their menu items are.
    """
    separator = QFrame()
    separator.setObjectName(label_roles.SEPARATOR)
    separator.setFrameShape(QFrame.Shape.VLine)
    separator.setFixedHeight(glyph_height)
    settings_btn = _tray_icon_button("⚙️", "Preferences…", glyph_height)
    bank_btn = _tray_icon_button("🏦", "Bank account", glyph_height)
    for btn in (settings_btn, bank_btn):
        btn.setEnabled(not read_only)
    return separator, settings_btn, bank_btn


def build_info_button(glyph_height: int) -> QPushButton:
    """Return the How It Works button shown right of the theme toggle.

    Always enabled: the help text is read-only, so viewers get it too.
    """
    return _tray_icon_button("ℹ️", "How it works", glyph_height)


def _report_saved(parent, dest: Path) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle("Save Successful")
    box.setText(f"Database saved to:\n{dest}")
    label_w = ui_scale.px(460)
    box.setStyleSheet(f"QLabel#qt_msgbox_label {{ min-width: {label_w}px; }}")
    box.exec()


def _copy_and_report(parent, conn, dest: Path) -> None:
    """Snapshot the LIVE database to `dest` through SQLite's backup API.

    Never a filesystem copy: the database is open and may be mid-transaction,
    so copying its bytes can produce a file the right length that no
    consistent state ever matched.
    """
    try:
        backup_open_database(conn, dest)
        _report_saved(parent, dest)
    except DatabaseCopyError as exc:
        QMessageBox.critical(parent, "Save Failed", str(exc))


def run_save_flow(parent, conn) -> None:
    """Save the database to the remembered location, confirming overwrite.

    With no remembered location yet this IS Save As: the user is prompted for
    a filename, defaulting to their Downloads folder.
    """
    target = load_save_location()
    if target is None:
        run_save_as_flow(parent, conn)
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
    _copy_and_report(parent, conn, target)


def run_save_as_flow(parent, conn) -> None:
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
    _copy_and_report(parent, conn, dest_path)


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


def run_load_flow(parent, db_path: Path, conn) -> Path | None:
    """Choose and validate a database to load; return it, else None.

    This deliberately does NOT put the file in place. The live database is
    open; replacing an open database underneath its own connection is what
    destroyed two real budgets: the connection carries on writing
    against a file that has been swapped out and the result is the right
    length and entirely zero bytes.

    So the decision is made here and the ACT is left to the composition
    root, which owns the connection and can close it first.

    Starts in the remembered save file's folder when one is set, else the
    user's Downloads folder.
    """
    remembered = load_save_location()
    start_dir = remembered.parent if remembered else default_downloads_dir()
    src, _ = QFileDialog.getOpenFileName(
        parent, "Load Database", str(start_dir), _DB_FILTER
    )
    if not src:
        return None
    src_path = Path(src)
    if src_path.resolve() == db_path.resolve():
        QMessageBox.warning(
            parent,
            "Load",
            "Selected file is the active database - nothing to load.",
        )
        return None

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
            return None

    validation_error = validate_db(src_path)
    if validation_error:
        QMessageBox.critical(
            parent,
            "Invalid Database",
            f"Cannot load - invalid ClearBudget database.\n\n{validation_error}",
        )
        return None

    return src_path
