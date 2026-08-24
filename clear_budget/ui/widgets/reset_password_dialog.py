"""ResetPasswordDialog - two-step password reset using the recovery code.

Split out of login_dialog.py to keep that module under the 400-line limit
(enforced by tests/structural/test_loc_limits.py) once the sign-in screen
grew its remembered-accounts controls. It is reached only from the sign-in
screen's "Forgot password?" link, which imports it where it is used so the
two modules do not have to import each other.
"""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from clear_budget.auth.user_store import UserStore
from clear_budget.ui import label_roles, ui_scale


def _input_style() -> str:
    """The sign-in screen's field styling, so the two screens match."""
    from clear_budget.ui.widgets.login_dialog import LoginDialog

    return LoginDialog._input_style()


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
        info.setObjectName(label_roles.SUBTLE)
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
            edit.setStyleSheet(_input_style())
            setattr(self, attr, edit)
            layout.addWidget(edit)

        self._err = QLabel("")
        self._err.setObjectName(label_roles.ERROR)
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
