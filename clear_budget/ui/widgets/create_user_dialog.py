"""CreateUserDialog - new account creation (first-run wizard, login screen, add-user)."""

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from clear_budget.auth.models import User
from clear_budget.auth.user_store import UserStore
from clear_budget.ui import ui_scale
from clear_budget.ui.widgets.login_dialog import LoginDialog

# Flags that give a titled dialog window WITHOUT a close button on Windows.
_NO_CLOSE_FLAGS = (
    Qt.WindowType.Dialog
    | Qt.WindowType.WindowTitleHint
    | Qt.WindowType.CustomizeWindowHint
)


class CreateUserDialog(QDialog):
    """Dialog for creating a new user account.

    On accepted, ``created_user`` holds the new User and
    ``recovery_code`` holds the plaintext code (shown once to the user).
    """

    def __init__(
        self,
        user_store: UserStore,
        is_first_user: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.user_store = user_store
        self.is_first_user = is_first_user
        self.created_user: User | None = None
        self.recovery_code: str = ""
        title = (
            "Welcome to Clear Budget - Create Your Account"
            if is_first_user
            else "Add User"
        )
        self.setWindowTitle(title)
        self.setMinimumWidth(ui_scale.px(420))
        if is_first_user:
            self.setWindowFlags(_NO_CLOSE_FLAGS)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(ui_scale.px(9))
        layout.setContentsMargins(
            ui_scale.px(28), ui_scale.px(22), ui_scale.px(28), ui_scale.px(22)
        )

        if self.is_first_user:
            intro = QLabel(
                "No user accounts exist yet.\n"
                "Create the first account - this will be the admin account."
            )
            intro.setWordWrap(True)
            intro.setStyleSheet("color: #94a3b8; font-size: 12px;")
            layout.addWidget(intro)
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color: #1e3a5f;")
            layout.addWidget(sep)

        lbl_user = QLabel("Username")
        lbl_user.setStyleSheet(ui_scale.style("font-size: 13px;"))
        layout.addWidget(lbl_user)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Choose a username")
        self.username_edit.setStyleSheet(LoginDialog._input_style())
        layout.addWidget(self.username_edit)

        lbl_pass = QLabel("Password  (min. 6 characters)")
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
        self.confirm_edit.returnPressed.connect(self._on_create)
        layout.addWidget(self.confirm_edit)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f87171; font-size: 12px;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        btn_layout = QHBoxLayout()
        if not self.is_first_user:
            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(self.reject)
            btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        create_btn = QPushButton("Create Account")
        create_btn.setDefault(True)
        create_btn.clicked.connect(self._on_create)
        btn_layout.addWidget(create_btn)
        layout.addLayout(btn_layout)

    def _on_create(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        confirm = self.confirm_edit.text()

        if not username:
            self._show_error("Username is required.")
            return
        if len(username) < 2:
            self._show_error("Username must be at least 2 characters.")
            return
        if not password:
            self._show_error("Password is required.")
            return
        if len(password) < 6:
            self._show_error("Password must be at least 6 characters.")
            return
        if password != confirm:
            self._show_error("Passwords do not match.")
            return
        if self.user_store.find_user(username) is not None:
            self._show_error(f"Username '{username}' is already taken.")
            return

        user, recovery_code = self.user_store.create_user(
            username, password, is_admin=self.is_first_user
        )
        self.created_user = user
        self.recovery_code = recovery_code
        self._show_recovery_code(recovery_code)
        self.accept()

    def _show_recovery_code(self, code: str) -> None:
        dlg = RecoveryCodeDialog(code, parent=self)
        dlg.exec()

    def _show_error(self, msg: str) -> None:
        self.error_label.setText(msg)
        self.error_label.setVisible(True)


class RecoveryCodeDialog(QDialog):
    """Displays the one-time recovery code after account creation.

    The close button is disabled - the user must tick the confirmation
    checkbox and click Continue to proceed.
    """

    def __init__(self, recovery_code: str, parent=None) -> None:
        super().__init__(parent)
        self._code = recovery_code
        self.setWindowTitle("Save Your Recovery Code")
        self.setMinimumWidth(ui_scale.px(460))
        self.setWindowFlags(_NO_CLOSE_FLAGS)
        self._build_ui(recovery_code)

    def _build_ui(self, code: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(ui_scale.px(10))
        layout.setContentsMargins(
            ui_scale.px(24), ui_scale.px(20), ui_scale.px(24), ui_scale.px(20)
        )

        warning = QLabel("⚠️  Save this recovery code in a safe place.")
        warning.setStyleSheet(
            ui_scale.style("font-size: 14px; font-weight: bold; color: #fbbf24;")
        )
        layout.addWidget(warning)

        info = QLabel(
            "This code is shown only once and cannot be recovered.\n"
            "If you forget your password, you will need this code to reset it."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(info)

        self._code_box = QTextEdit()
        self._code_box.setPlainText(code)
        self._code_box.setReadOnly(True)
        self._code_box.setFixedHeight(ui_scale.px(52))
        self._code_box.setStyleSheet(
            ui_scale.style(
                "QTextEdit {"
                "  font-family: monospace;"
                "  font-size: 15px;"
                "  background-color: #0d1b2a;"
                "  color: #34d399;"
                "  border: 1px solid #1e3a5f;"
                "  border-radius: 4px;"
                "  padding: 6px;"
                "}"
            )
        )
        layout.addWidget(self._code_box)

        copy_btn = QPushButton("⧉  Copy code to clipboard")
        copy_btn.setStyleSheet(
            ui_scale.style("QPushButton { font-size: 13px; padding: 4px 10px; }")
        )
        copy_btn.clicked.connect(self._copy_to_clipboard)
        layout.addWidget(copy_btn)

        self._confirm_check = QCheckBox(
            "I have saved my recovery code in a safe place."
        )
        self._confirm_check.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self._confirm_check.stateChanged.connect(self._on_confirm_changed)
        layout.addWidget(self._confirm_check)

        self._ok_btn = QPushButton("Continue")
        self._ok_btn.setDefault(True)
        self._ok_btn.setEnabled(False)  # locked until checkbox ticked
        self._ok_btn.clicked.connect(self.accept)
        layout.addWidget(self._ok_btn)

    def _copy_to_clipboard(self) -> None:
        QApplication.clipboard().setText(self._code)

    def _on_confirm_changed(self, state: int) -> None:
        self._ok_btn.setEnabled(state == Qt.CheckState.Checked.value)
