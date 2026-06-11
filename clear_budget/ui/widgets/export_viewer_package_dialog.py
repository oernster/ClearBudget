"""ExportViewerPackageDialog - admin dialog to bundle a read-only viewer package."""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from clear_budget.auth.viewer_package import export_viewer_package
from clear_budget.ui import ui_scale
from clear_budget.ui.widgets.login_dialog import LoginDialog


class ExportViewerPackageDialog(QDialog):
    """Prompt for new viewer credentials, then save a .zip viewer package."""

    def __init__(self, db_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("Export Read-Only Viewer Package")
        self.setMinimumWidth(ui_scale.px(440))
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(ui_scale.px(9))
        layout.setContentsMargins(
            ui_scale.px(28), ui_scale.px(22), ui_scale.px(28), ui_scale.px(22)
        )

        intro = QLabel(
            "Choose a username and password for the read-only viewer.\n"
            "Give these credentials and the exported file to the person\n"
            "who should have view-only access to this data on their own\n"
            "computer."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(intro)

        lbl_user = QLabel("Viewer Username")
        lbl_user.setStyleSheet(ui_scale.style("font-size: 13px;"))
        layout.addWidget(lbl_user)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Choose a username")
        self.username_edit.setStyleSheet(LoginDialog._input_style())
        layout.addWidget(self.username_edit)

        lbl_pass = QLabel("Viewer Password  (min. 6 characters)")
        lbl_pass.setStyleSheet(ui_scale.style("font-size: 13px;"))
        layout.addWidget(lbl_pass)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Choose a password")
        self.password_edit.setStyleSheet(LoginDialog._input_style())
        layout.addWidget(self.password_edit)

        lbl_confirm = QLabel("Confirm Password")
        lbl_confirm.setStyleSheet(ui_scale.style("font-size: 13px;"))
        layout.addWidget(lbl_confirm)
        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_edit.setPlaceholderText("Repeat password")
        self.confirm_edit.setStyleSheet(LoginDialog._input_style())
        self.confirm_edit.returnPressed.connect(self._on_export)
        layout.addWidget(self.confirm_edit)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f87171; font-size: 12px;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        export_btn = QPushButton("Export Package…")
        export_btn.setDefault(True)
        export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(export_btn)
        layout.addLayout(btn_layout)

    def _on_export(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        confirm = self.confirm_edit.text()

        if not username or len(username) < 2:
            self._show_error("Username must be at least 2 characters.")
            return
        if len(password) < 6:
            self._show_error("Password must be at least 6 characters.")
            return
        if password != confirm:
            self._show_error("Passwords do not match.")
            return

        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export Viewer Package",
            str(Path.home() / f"clearbudget_viewer_{username}.zip"),
            "ClearBudget Viewer Package (*.zip)",
        )
        if not dest:
            return
        dest_path = Path(dest)
        if dest_path.suffix.lower() != ".zip":
            dest_path = dest_path.with_suffix(".zip")

        try:
            export_viewer_package(self.db_path, dest_path, username, password)
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            return

        QMessageBox.information(
            self,
            "Export Successful",
            f"Viewer package exported to:\n{dest_path}\n\n"
            "Give this file and the credentials below to the viewer - they\n"
            'should use "Import Viewer Package" on the sign-in screen of\n'
            "their own ClearBudget install:\n\n"
            f"Username: {username}\nPassword: {password}",
        )
        self.accept()

    def _show_error(self, msg: str) -> None:
        self.error_label.setText(msg)
        self.error_label.setVisible(True)
