"""Save, Save As and Load flows for the budget database.

Save snapshots the live database to the remembered save file (prompting to
overwrite when it already exists); the first ever Save behaves as Save As,
prompting for a filename and defaulting to the app's own data directory. The
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

import sqlite3
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from clear_budget.shared.db_copy import DatabaseCopyError, backup_open_database
from clear_budget.shared.db_validation import is_accounts_database, validate_db
from clear_budget.ui import ui_scale
from clear_budget.ui.save_location import load_save_location, store_save_location
from clear_budget.ui.ui_paths import default_data_dir

# Default backup filename offered the first time the user saves.
_DEFAULT_SAVE_NAME = "clearbudget_backup.db"
_DB_FILTER = "ClearBudget Database (*.db)"


def _report_saved(parent, dest: Path) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle("Save Successful")
    box.setText(f"Database saved to:\n{dest}")
    label_w = ui_scale.px(460)
    box.setStyleSheet(f"QLabel#qt_msgbox_label {{ min-width: {label_w}px; }}")
    box.exec()


def live_database_path(conn) -> Path | None:
    """The file `conn` has open, resolved; None if it cannot be determined.

    Asked of the CONNECTION rather than reconstructed from the settings, so
    it is right by construction whichever database this session opened.
    """
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
    except sqlite3.Error:
        return None
    filename = row[2] if row else ""
    if not filename:
        return None
    try:
        return Path(filename).resolve()
    except OSError:
        return None


def is_live_database(conn, dest: Path) -> bool:
    """Whether `dest` IS the database currently open on `conn`."""
    live = live_database_path(conn)
    if live is None:
        return False
    try:
        return dest.resolve() == live
    except OSError:
        return False


def _save_in_place(parent, conn, dest: Path) -> None:
    """Saving the live database over itself: commit, then say so.

    Emphatically NOT a copy. The snapshot path builds a scratch file and
    renames it over the destination; the destination here is the open
    database, so the rename is the exact operation `replace_closed_database`
    exists to forbid: replacing a file underneath a live connection is what
    destroyed two real budgets. Windows refuses it outright, which is how
    this surfaced, as "[WinError 5] Access is denied" on a `.partial` rename.
    Linux and macOS would have ALLOWED the rename and left the connection
    writing to a file no longer reachable by that name, so the error was the
    good outcome and the fix is not to make the rename work.

    Committing is the whole operation; it is enough. The journal mode is
    `delete`, so a committed transaction is already in the `.db` file itself;
    once the in-flight write is committed, the file at this path IS the
    current budget. There is nothing left to copy from or to.
    """
    try:
        if conn.in_transaction:
            conn.commit()
    except sqlite3.Error as exc:
        QMessageBox.critical(parent, "Save Failed", str(exc))
        return
    _report_saved(parent, dest)


def _copy_and_report(parent, conn, dest: Path) -> None:
    """Snapshot the LIVE database to `dest` through SQLite's backup API.

    Never a filesystem copy: the database is open and may be mid-transaction,
    so copying its bytes can produce a file the right length that no
    consistent state ever matched.

    Saving ONTO the live database is not a snapshot at all; see
    `_save_in_place`. It is offered rather than refused because the answer to
    "why can I not save my budget over my budget" is that it is already
    saved, which is a success and not an error.
    """
    if is_live_database(conn, dest):
        _save_in_place(parent, conn, dest)
        return
    try:
        backup_open_database(conn, dest)
        _report_saved(parent, dest)
    except DatabaseCopyError as exc:
        QMessageBox.critical(parent, "Save Failed", str(exc))


def run_save_flow(parent, conn) -> None:
    """Save the database to the remembered location, confirming overwrite.

    With no remembered location yet this IS Save As: the user is prompted
    for a filename, defaulting to the app's own data directory.
    """
    target = load_save_location()
    if target is None:
        run_save_as_flow(parent, conn)
        return
    # Nothing is being overwritten when the target IS the open database, so
    # asking would be a question about a file that is not at risk.
    if target.exists() and not is_live_database(conn, target):
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
    """Prompt for a save file, remember it, then save the database to it.

    Defaults to the app's own data directory, where the live databases are.
    A saved budget is a copy of one of those and is loaded back into the same
    application, so it has no reason to be filed with the downloads.
    """
    remembered = load_save_location()
    start = remembered if remembered else default_data_dir() / _DEFAULT_SAVE_NAME
    dest, _ = QFileDialog.getSaveFileName(
        parent, "Save Database As", str(start), _DB_FILTER
    )
    if not dest:
        return
    dest_path = Path(dest)
    if dest_path.suffix.lower() != ".db":
        dest_path = dest_path.with_suffix(".db")
    # A save location that IS the open database would make every later Save a
    # silent no-op, so the choice is honoured once and not remembered. Save
    # then keeps prompting, which is the truthful state: there is no separate
    # backup file yet.
    if not is_live_database(conn, dest_path):
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


def run_load_flow(
    parent, db_path: Path, conn, current_username: str, user_store
) -> Path | None:
    """Choose and validate a database to load; return it, else None.

    This deliberately does NOT put the file in place. The live database is
    open; replacing an open database underneath its own connection is what
    destroyed two real budgets: the connection carries on writing
    against a file that has been swapped out and the result is the right
    length and entirely zero bytes.

    So the decision is made here and the ACT is left to the composition
    root, which owns the connection and can close it first.

    Starts in the remembered save file's folder when one is set, else the
    app's own data directory, which is where Save As offered to put it.
    """
    remembered = load_save_location()
    start_dir = remembered.parent if remembered else default_data_dir()
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

    # EVERY refusal happens before the overwrite question. That question
    # threatens to destroy the budget in front of the user, so asking it about
    # a file that is then rejected is a threat made over nothing: picking the
    # accounts store used to warn that all bills, income and cards were about
    # to be replaced, then afterwards admit it was never loadable.
    if is_accounts_database(src_path):
        QMessageBox.critical(
            parent,
            "That Is the Accounts File",
            "The file you chose is the ClearBudget accounts file, which holds "
            "who may sign in. It is not a budget and it cannot be loaded as "
            "one.\n\n"
            "Budgets are named after the account they belong to, such as "
            "budget_<account>.db. Nothing has been changed.",
        )
        return None

    validation_error = validate_db(src_path)
    if validation_error:
        QMessageBox.critical(
            parent,
            "Invalid Database",
            f"Cannot load - invalid ClearBudget database.\n\n{validation_error}",
        )
        return None

    # Validating the SCHEMA said nothing about WHOSE budget this is, while
    # every account's file sits in the directory this dialog opens on. A file owned by
    # another account opens only when that account proves itself.
    from clear_budget.ui.widgets._owner_challenge import owner_permits_load

    if not owner_permits_load(parent, src_path, current_username, user_store):
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

    return src_path
