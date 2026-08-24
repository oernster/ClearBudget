"""BudgetsDialog - list, create, rename, switch and delete named budgets.

One user can own several budgets, each its own database file. This dialog is
where that set is managed. It replaces the old "New Budget" wipe, which could
only make a budget by destroying the one you had.

Nothing here edits budget CONTENT. Creating a budget registers an empty one and
makes it active; the window then reloads onto it through the same
`database_replaced` path an import already used, so the dialog never has to
know how a session is built.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from clear_budget.shared.budget_registry import (
    BudgetRegistryError,
    create_budget,
    delete_budget,
    load_index,
    rename_budget,
    set_active,
)
from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui.widgets.first_stop_dialog import FirstStopDialog
from clear_budget.ui.utils.table_focus import keyboard_only_focus
from clear_budget.ui.utils.text_metrics import apply_comfortable_rows

_ACTIVE_MARK = "Active"
_MAX_NAME_LEN = 60
_TITLE_STYLE = "font-size: 16px; font-weight: bold;"


def prompt_budget_name(
    parent, title: str, prompt: str, initial: str = ""
) -> str | None:
    """Prompt for a budget name; None when cancelled or left blank.

    Module level rather than a dialog method because File | New Budget asks
    the same question without opening the manager at all.
    """
    name, ok = QInputDialog.getText(parent, title, prompt, text=initial)
    if not ok or not name.strip():
        return None
    return name.strip()[:_MAX_NAME_LEN]


class BudgetsDialog(FirstStopDialog):
    """Manage the budgets belonging to one user."""

    def __init__(self, username: str, parent=None) -> None:
        super().__init__(parent)
        self.username = username
        # Set when the ACTIVE budget changes, by switching to another or by
        # creating one. The caller reads it to decide whether to reload the
        # window; renaming and deleting an inactive budget leave it False.
        self.active_changed = False
        self.setWindowTitle("Budgets")
        self.setMinimumWidth(ui_scale.px(520))
        self.setMinimumHeight(ui_scale.px(340))
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(ui_scale.px(8))
        layout.setContentsMargins(
            ui_scale.px(20), ui_scale.px(16), ui_scale.px(20), ui_scale.px(16)
        )

        title = QLabel("Your budgets")
        title.setStyleSheet(ui_scale.style(_TITLE_STYLE))
        layout.addWidget(title)

        hint = QLabel(
            "Each budget is separate: its own bills, income, cards and settings. "
            "Switching between them never changes what is in either. To delete "
            "the budget you are in, switch to another one first."
        )
        hint.setObjectName(label_roles.HINT)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget()
        apply_comfortable_rows(self.table)
        keyboard_only_focus(self.table)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Budget", ""])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # One ring stop, not one per cell, exactly as the user table does it:
        # the cells are read-only, so walking them with Tab gives nothing.
        self.table.setTabKeyNavigation(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._sync_buttons)
        self.table.itemDoubleClicked.connect(self._on_switch)
        layout.addWidget(self.table)

        layout.addLayout(self._build_button_row())

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    def _build_button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.new_btn = QPushButton("New Budget…")
        self.new_btn.clicked.connect(self._on_new)
        self.switch_btn = QPushButton("Switch To")
        self.switch_btn.clicked.connect(self._on_switch)
        self.rename_btn = QPushButton("Rename…")
        self.rename_btn.clicked.connect(self._on_rename)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete)
        row.addWidget(self.new_btn)
        row.addWidget(self.switch_btn)
        row.addWidget(self.rename_btn)
        row.addStretch()
        row.addWidget(self.delete_btn)
        return row

    def _refresh(self) -> None:
        """Rebuild the table from the registry and re-arm the buttons."""
        index = load_index(self.username)
        self._records = index.budgets
        self._active_slug = index.active_record().slug
        self.table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            self.table.setItem(row, 0, QTableWidgetItem(record.name))
            mark = _ACTIVE_MARK if record.slug == self._active_slug else ""
            self.table.setItem(row, 1, QTableWidgetItem(mark))
            if record.slug == self._active_slug:
                self.table.selectRow(row)
        self._sync_buttons()

    def _selected(self):
        """The selected budget record; None when nothing is selected."""
        row = self.table.currentRow()
        if row < 0 or row >= len(self._records) or not self.table.selectionModel():
            return None
        if not self.table.selectionModel().isRowSelected(row):
            return None
        return self._records[row]

    def _sync_buttons(self) -> None:
        """Arm each button for what the current selection actually allows.

        Switch and Delete are both dead on the budget already OPEN. For switch
        that is merely pointless; for delete it is a hard constraint, because
        the active budget's database is held open by this session and Windows
        refuses to unlink an open file. Switching away first is the route; it
        also means the last remaining budget can never be deleted, since it
        is always the active one.

        Both are disabled rather than left live to fail: a control that
        explains itself by refusing is worse than one that shows it cannot act.
        """
        record = self._selected()
        chosen = record is not None
        inactive = chosen and record.slug != self._active_slug
        self.rename_btn.setEnabled(chosen)
        self.switch_btn.setEnabled(inactive)
        self.delete_btn.setEnabled(inactive)

    def _report(self, error: Exception) -> None:
        QMessageBox.warning(self, "Budgets", str(error))

    def _on_new(self) -> None:
        name = prompt_budget_name(
            self,
            "New Budget",
            "Name for the new budget:\n\n"
            "It starts empty. Your current budget is left exactly as it is.",
        )
        if name is None:
            return
        try:
            create_budget(self.username, name)
        except BudgetRegistryError as exc:
            self._report(exc)
            return
        self.active_changed = True
        self.accept()

    def _on_switch(self) -> None:
        record = self._selected()
        if record is None or record.slug == self._active_slug:
            return
        try:
            set_active(self.username, record.slug)
        except BudgetRegistryError as exc:
            self._report(exc)
            self._refresh()
            return
        self.active_changed = True
        self.accept()

    def _on_rename(self) -> None:
        record = self._selected()
        if record is None:
            return
        name = prompt_budget_name(self, "Rename Budget", "New name:", record.name)
        if name is None:
            return
        try:
            rename_budget(self.username, record.slug, name)
        except BudgetRegistryError as exc:
            self._report(exc)
        self._refresh()

    def _on_delete(self) -> None:
        record = self._selected()
        if record is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Budget",
            f"Permanently delete the budget '{record.name}'?\n\n"
            "Its bills, income sources, credit cards, overrides and settings "
            "all go with it. This cannot be undone.\n\n"
            "Your other budgets are not affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_budget(self.username, record.slug)
        except (BudgetRegistryError, OSError) as exc:
            self._report(exc)
        self._refresh()
