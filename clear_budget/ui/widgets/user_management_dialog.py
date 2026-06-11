"""UserManagementDialog - admin screen to view and manage user accounts."""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)
from PySide6.QtCore import Qt

from clear_budget.auth.user_store import UserStore
from clear_budget.auth.models import User
from clear_budget.shared.config import Config
from clear_budget.ui import ui_scale


class UserManagementDialog(QDialog):
    """Admin dialog to list users, add new ones, and delete existing ones."""

    def __init__(
        self,
        user_store: UserStore,
        current_user: User,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.user_store = user_store
        self.current_user = current_user
        self.setWindowTitle("Manage Users")
        self.setMinimumWidth(ui_scale.px(500))
        self.setMinimumHeight(ui_scale.px(320))
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(ui_scale.px(8))
        layout.setContentsMargins(
            ui_scale.px(20), ui_scale.px(16), ui_scale.px(20), ui_scale.px(16)
        )

        title = QLabel("User Accounts")
        title.setStyleSheet(ui_scale.style("font-size: 16px; font-weight: bold;"))
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Username", "Role", "ID"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setStretchLastSection(False)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add User")
        self.add_btn.clicked.connect(self._on_add_user)
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete_user)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.delete_btn)
        layout.addLayout(btn_layout)

        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _refresh(self) -> None:
        users = self.user_store.get_all_users()
        self.table.setRowCount(0)
        for user in users:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_item = QTableWidgetItem(user.username)
            name_item.setData(Qt.ItemDataRole.UserRole, user.id)
            if user.id == self.current_user.id:
                name_item.setText(f"{user.username}  (you)")
                name_item.setForeground(Qt.GlobalColor.cyan)
            self.table.setItem(row, 0, name_item)
            role = "Admin" if user.is_admin else "User"
            self.table.setItem(row, 1, QTableWidgetItem(role))
            self.table.setItem(row, 2, QTableWidgetItem(str(user.id)))

    def _on_selection_changed(self) -> None:
        """Enable Delete only when a row other than the current user is selected."""
        row = self.table.currentRow()
        if row < 0:
            self.delete_btn.setEnabled(False)
            return
        item = self.table.item(row, 0)
        if item is None:
            self.delete_btn.setEnabled(False)
            return
        uid = item.data(Qt.ItemDataRole.UserRole)
        self.delete_btn.setEnabled(uid != self.current_user.id)

    def _on_add_user(self) -> None:
        from clear_budget.ui.widgets.create_user_dialog import CreateUserDialog

        dlg = CreateUserDialog(self.user_store, is_first_user=False, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh()

    def _on_delete_user(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Delete User", "Select a user first.")
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        uid = item.data(Qt.ItemDataRole.UserRole)
        username = item.text()
        if uid == self.current_user.id:
            QMessageBox.warning(
                self, "Delete User", "You cannot delete your own account."
            )
            return

        confirm = QMessageBox.warning(
            self,
            "Delete User",
            f"Permanently delete user account '{username}' and all of"
            f" their budget data?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        confirm = QMessageBox.warning(
            self,
            "Delete User",
            f"Are you sure? '{username}' and all of their budget data will"
            f" be permanently and irreversibly deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.user_store.delete_user(uid)
        self._delete_user_data(username)
        self._refresh()

    @classmethod
    def _delete_user_data(cls, username: str) -> None:
        """Delete the per-user budget database file and its sidecar files."""
        cls._delete_db_files(Config.for_user(username).db_path)

    @staticmethod
    def _delete_db_files(db_path: Path) -> None:
        for suffix in ("", "-wal", "-shm", "-journal"):
            path = db_path.with_name(db_path.name + suffix)
            if path.exists():
                path.unlink()
