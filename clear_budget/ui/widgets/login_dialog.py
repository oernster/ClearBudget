"""Login dialog - shown at startup and on lock/switch-user."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from pathlib import Path

from clear_budget.auth.user_store import UserStore
from clear_budget.auth.models import User
from clear_budget.ui import ui_scale
from clear_budget.ui.widgets._viewer_package_import_flow import (
    run_import_viewer_package_flow,
)


class LoginDialog(QDialog):
    """Username/password login screen.

    On accepted, ``authenticated_user`` holds the logged-in User.
    """

    def __init__(self, user_store: UserStore, parent=None) -> None:
        super().__init__(parent)
        self.user_store = user_store
        self.authenticated_user: User | None = None
        self.setWindowTitle("Clear Budget - Sign In")
        self.setMinimumWidth(ui_scale.px(380))
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(ui_scale.px(10))
        layout.setContentsMargins(
            ui_scale.px(32), ui_scale.px(28), ui_scale.px(32), ui_scale.px(24)
        )

        # Logo / title
        logo_path = Path(__file__).resolve().parents[3] / "clearbudget_64.png"
        if logo_path.exists():
            lbl = QLabel()
            pm = QPixmap(str(logo_path))
            lbl.setPixmap(
                pm.scaledToHeight(
                    ui_scale.px(48), Qt.TransformationMode.SmoothTransformation
                )
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)

        title = QLabel("Clear Budget")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            ui_scale.style(
                "font-size: 22px; font-weight: bold;"
                " color: #00d4ff; margin-bottom: 4px;"
            )
        )
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #1e3a5f;")
        layout.addWidget(sep)

        layout.addSpacing(ui_scale.px(4))

        # Username
        lbl_user = QLabel("Username")
        lbl_user.setStyleSheet(ui_scale.style("font-size: 13px;"))
        layout.addWidget(lbl_user)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Enter username")
        self.username_edit.setStyleSheet(self._input_style())
        layout.addWidget(self.username_edit)

        # Password
        lbl_pass = QLabel("Password")
        lbl_pass.setStyleSheet(ui_scale.style("font-size: 13px;"))
        layout.addWidget(lbl_pass)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Enter password")
        self.password_edit.setStyleSheet(self._input_style())
        self.password_edit.returnPressed.connect(self._on_login)
        layout.addWidget(self.password_edit)

        # Error label (hidden until needed)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f87171; font-size: 12px;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        layout.addSpacing(ui_scale.px(4))

        # Buttons grid: links on the left, action buttons on the right
        grid = QGridLayout()
        grid.setHorizontalSpacing(ui_scale.px(12))
        grid.setVerticalSpacing(ui_scale.px(8))

        self.forgot_btn = QPushButton("Forgot password?")
        self.forgot_btn.setFlat(True)
        self.forgot_btn.setStyleSheet(self._link_style())
        self.forgot_btn.clicked.connect(self._on_forgot_password)
        grid.addWidget(self.forgot_btn, 0, 0, Qt.AlignmentFlag.AlignLeft)

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setDefault(True)
        self.login_btn.setMinimumWidth(ui_scale.px(90))
        self.login_btn.clicked.connect(self._on_login)
        grid.addWidget(self.login_btn, 0, 1)

        self.import_viewer_btn = QPushButton("Import Viewer Package…")
        self.import_viewer_btn.setFlat(True)
        self.import_viewer_btn.setStyleSheet(self._link_style())
        self.import_viewer_btn.clicked.connect(self._on_import_viewer_package)
        grid.addWidget(self.import_viewer_btn, 1, 0, Qt.AlignmentFlag.AlignLeft)

        self.create_account_btn = QPushButton("Create Account")
        self.create_account_btn.clicked.connect(self._on_create_account)
        grid.addWidget(self.create_account_btn, 1, 1)

        grid.setColumnStretch(0, 1)
        layout.addLayout(grid)

    @staticmethod
    def _link_style() -> str:
        return ui_scale.style(
            "QPushButton { color: #60a5fa; font-size: 12px;"
            " border: none; background: transparent; padding: 0; margin: 0; }"
            "QPushButton:hover { color: #93c5fd; text-decoration: underline; }"
        )

    @staticmethod
    def _input_style() -> str:
        return ui_scale.style(
            "QLineEdit {"
            "  background-color: #0d1b2a;"
            "  color: #e2e8f0;"
            "  border: 1px solid #1e3a5f;"
            "  border-radius: 4px;"
            "  padding: 6px 8px;"
            "  font-size: 14px;"
            "}"
            "QLineEdit:focus {"
            "  border-color: #00d4ff;"
            "}"
        )

    def _on_login(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if not username or not password:
            self._show_error("Enter both username and password.")
            return
        user = self.user_store.verify_password(username, password)
        if user is None:
            self._show_error("Incorrect username or password.")
            self.password_edit.clear()
            self.password_edit.setFocus()
            return
        self.authenticated_user = user
        self.accept()

    def _on_import_viewer_package(self) -> None:
        user = run_import_viewer_package_flow(self, self.user_store)
        if user is None:
            return

        self.username_edit.setText(user.username)
        self.password_edit.clear()
        self.password_edit.setFocus()
        QMessageBox.information(
            self,
            "Import Successful",
            f"Viewer account '{user.username}' is ready.\n\n"
            "Enter the password you were given and sign in.",
        )

    def _on_create_account(self) -> None:
        from clear_budget.ui.widgets.create_user_dialog import CreateUserDialog

        dlg = CreateUserDialog(self.user_store, is_first_user=False, parent=self)
        if (
            dlg.exec() != CreateUserDialog.DialogCode.Accepted
            or dlg.created_user is None
        ):
            return

        self.username_edit.setText(dlg.created_user.username)
        self.password_edit.clear()
        self.password_edit.setFocus()
        QMessageBox.information(
            self,
            "Account Created",
            f"Account '{dlg.created_user.username}' has been created.\n\n"
            "Enter your password and sign in.",
        )

    def _on_forgot_password(self) -> None:
        dlg = ResetPasswordDialog(self.user_store, parent=self)
        dlg.exec()

    def _show_error(self, msg: str) -> None:
        self.error_label.setText(msg)
        self.error_label.setVisible(True)


class ResetPasswordDialog(QDialog):
    """Two-step password reset using the recovery code."""

    def __init__(self, user_store: UserStore, parent=None) -> None:
        super().__init__(parent)
        self.user_store = user_store
        self.setWindowTitle("Reset Password")
        self.setMinimumWidth(ui_scale.px(400))
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(ui_scale.px(8))
        layout.setContentsMargins(
            ui_scale.px(24), ui_scale.px(20), ui_scale.px(24), ui_scale.px(20)
        )

        info = QLabel(
            "Enter your username and the recovery code that was shown when your\n"
            "account was created, then choose a new password."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(info)

        layout.addSpacing(ui_scale.px(4))

        for attr, label_text, placeholder, echo in [
            ("_r_user", "Username", "Your username", QLineEdit.EchoMode.Normal),
            (
                "_r_code",
                "Recovery Code",
                "Paste your recovery code",
                QLineEdit.EchoMode.Normal,
            ),
            ("_r_pass1", "New Password", "New password", QLineEdit.EchoMode.Password),
            (
                "_r_pass2",
                "Confirm New Password",
                "Repeat new password",
                QLineEdit.EchoMode.Password,
            ),
        ]:
            lbl = QLabel(label_text)
            lbl.setStyleSheet(ui_scale.style("font-size: 13px;"))
            layout.addWidget(lbl)
            edit = QLineEdit()
            edit.setEchoMode(echo)
            edit.setPlaceholderText(placeholder)
            edit.setStyleSheet(LoginDialog._input_style())
            setattr(self, attr, edit)
            layout.addWidget(edit)

        self._err = QLabel("")
        self._err.setStyleSheet("color: #f87171; font-size: 12px;")
        self._err.setVisible(False)
        layout.addWidget(self._err)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("Reset Password")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_reset)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _on_reset(self) -> None:
        username = self._r_user.text().strip()
        code = self._r_code.text().strip()
        pw1 = self._r_pass1.text()
        pw2 = self._r_pass2.text()

        if not all([username, code, pw1, pw2]):
            self._show_error("All fields are required.")
            return
        if pw1 != pw2:
            self._show_error("Passwords do not match.")
            return
        if len(pw1) < 6:
            self._show_error("Password must be at least 6 characters.")
            return
        if self.user_store.find_user(username) is None:
            self._show_error("No account with that username exists.")
            return
        if not self.user_store.verify_recovery_code(username, code):
            self._show_error("Recovery code is incorrect.")
            return

        self.user_store.change_password(username, pw1)
        QMessageBox.information(
            self,
            "Password Reset",
            "Password changed successfully. You can now sign in.",
        )
        self.accept()

    def _show_error(self, msg: str) -> None:
        self._err.setText(msg)
        self._err.setVisible(True)
