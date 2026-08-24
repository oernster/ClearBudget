"""Login dialog - shown at startup and on lock/switch-user."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from clear_budget.auth.models import User
from clear_budget.auth.remembered_login import RememberedLogin
from clear_budget.auth.user_store import UserStore
from clear_budget.shared.resources import find_logo_png_path
from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui.widgets._login_styles import (
    combo_style,
    input_style,
    link_style,
)
from clear_budget.ui.widgets._viewer_package_import_flow import (
    run_import_viewer_package_flow,
)

# How many remembered accounts it takes for the username field to become a
# dropdown. With one there is no choice to offer, so a dropdown would only
# make the field harder to type into.
_DROPDOWN_FROM = 2


class LoginDialog(QDialog):
    """Username/password login screen.

    On accepted, ``authenticated_user`` holds the logged-in User.
    """

    def __init__(
        self,
        user_store: UserStore,
        remembered_login: RememberedLogin | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.user_store = user_store
        self.remembered_login = remembered_login
        self.authenticated_user: User | None = None
        self.setWindowTitle("ClearBudget - Sign In")
        self.setMinimumWidth(ui_scale.px(380))
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self._build_ui()
        self._prefill_remembered()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(ui_scale.px(10))
        layout.setContentsMargins(
            ui_scale.px(32), ui_scale.px(28), ui_scale.px(32), ui_scale.px(24)
        )

        # Logo / title. Resolved through the shared asset lookup, never by
        # counting parents from this module: doing that reached a 64px file at
        # the repository root, which exists in a source checkout and in the
        # Windows bundle but not in the Flatpak or the macOS app, so the logo
        # was quietly missing on two platforms out of three. `exists()` made
        # that failure silent rather than loud.
        logo_path = find_logo_png_path()
        if logo_path is not None:
            lbl = QLabel()
            pm = QPixmap(str(logo_path))
            lbl.setPixmap(
                pm.scaledToHeight(
                    ui_scale.px(48), Qt.TransformationMode.SmoothTransformation
                )
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)

        title = QLabel("ClearBudget")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName(label_roles.LOGIN_TITLE)
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName(label_roles.SEPARATOR)
        layout.addWidget(sep)

        layout.addSpacing(ui_scale.px(4))

        # Username. A plain field until there is more than one account to
        # choose between, because a dropdown of one is a field that has learnt
        # to be harder to type in.
        lbl_user = QLabel("Username")
        lbl_user.setStyleSheet(ui_scale.style("font-size: 13px;"))
        layout.addWidget(lbl_user)
        layout.addWidget(self._build_username_control())

        # Password
        lbl_pass = QLabel("Password")
        lbl_pass.setStyleSheet(ui_scale.style("font-size: 13px;"))
        layout.addWidget(lbl_pass)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Enter password")
        self.password_edit.setStyleSheet(input_style())
        self.password_edit.returnPressed.connect(self._on_login)
        layout.addWidget(self.password_edit)

        # Two ticks, not one. Remembering a username is a convenience;
        # remembering a password is a trust decision, so one must never imply
        # the other. The password tick is live only while the username one is,
        # since a password has nowhere to be filed without a name.
        self.remember_user_check = QCheckBox("Remember my username")
        self.remember_password_check = QCheckBox("Remember my password")
        for check in (self.remember_user_check, self.remember_password_check):
            check.setStyleSheet(ui_scale.style("font-size: 13px;"))
            check.setVisible(self.remembered_login is not None)
            layout.addWidget(check)
        self.remember_user_check.toggled.connect(self._on_remember_user_toggled)
        self.remember_password_check.setEnabled(False)

        # Error label (hidden until needed)
        self.error_label = QLabel("")
        self.error_label.setObjectName(label_roles.ERROR)
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
        self.forgot_btn.setStyleSheet(link_style())
        self.forgot_btn.clicked.connect(self._on_forgot_password)
        grid.addWidget(self.forgot_btn, 0, 0, Qt.AlignmentFlag.AlignLeft)

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setDefault(True)
        self.login_btn.setMinimumWidth(ui_scale.px(90))
        self.login_btn.clicked.connect(self._on_login)
        grid.addWidget(self.login_btn, 0, 1)

        self.import_viewer_btn = QPushButton("Import Viewer Package…")
        self.import_viewer_btn.setFlat(True)
        self.import_viewer_btn.setStyleSheet(link_style())
        self.import_viewer_btn.clicked.connect(self._on_import_viewer_package)
        grid.addWidget(self.import_viewer_btn, 1, 0, Qt.AlignmentFlag.AlignLeft)

        self.create_account_btn = QPushButton("Create Account")
        self.create_account_btn.clicked.connect(self._on_create_account)
        grid.addWidget(self.create_account_btn, 1, 1)

        grid.setColumnStretch(0, 1)
        layout.addLayout(grid)

    def _build_username_control(self):
        """The username field, as a dropdown when there is a choice to offer.

        Only REMEMBERED accounts are listed. An account that never ticked the
        box does not appear, so the screen never becomes a directory of who
        holds an account on this machine for whoever is sitting at it. The
        dropdown stays editable, so a name that is not on it can still be
        typed straight in.
        """
        remembered = (
            () if self.remembered_login is None else self.remembered_login.usernames()
        )
        if len(remembered) < _DROPDOWN_FROM:
            self.username_combo = None
            self.username_edit = QLineEdit()
            self.username_edit.setStyleSheet(input_style())
        else:
            self.username_combo = QComboBox()
            self.username_combo.setEditable(True)
            self.username_combo.addItems(remembered)
            # textActivated, never currentTextChanged: the latter fires on
            # every KEYSTROKE in an editable combo, so typing a name emptied
            # the password box letter by letter on the way to it. This one
            # fires only when an entry is actually chosen.
            self.username_combo.textActivated.connect(self._on_username_chosen)
            # The box drawn on screen is the COMBO, so the combo is what gets
            # the field styling. Styling only its inner line edit left an
            # unthemed control with no visible arrow, reading as a plain
            # field; it also left that edit on a 27px point-sized font inside
            # a 29px box, which clipped the name it was showing.
            self.username_combo.setStyleSheet(combo_style())
            self.username_edit = self.username_combo.lineEdit()
        self.username_edit.setPlaceholderText("Enter username")
        return self.username_combo or self.username_edit

    def _prefill_remembered(self) -> None:
        """Offer the account that signed in last, filled in as far as it asked."""
        if self.remembered_login is None:
            return
        remembered = self.remembered_login.usernames()
        if not remembered:
            return
        # Falling back to the first remembered account matters: nothing has
        # signed in yet on a machine whose only account was remembered when
        # it was CREATED; offering an empty screen there would read as the
        # checkbox never having worked.
        username = self.remembered_login.last_username() or remembered[0]
        self.username_edit.setText(username)
        self._fill_for(username)
        if self.password_edit.text():
            self.login_btn.setFocus()

    def _on_username_chosen(self, username: str) -> None:
        """Re-fill the password and the ticks for the account now selected."""
        self._fill_for(username.strip())

    def _fill_for(self, username: str) -> None:
        """Show what is remembered about `username`; nothing about anyone else."""
        if self.remembered_login is None:
            return
        known = username in self.remembered_login.usernames()
        password = self.remembered_login.recall_password(username)
        self.password_edit.setText(password or "")
        self.remember_user_check.setChecked(known)
        self.remember_password_check.setChecked(password is not None)

    def _on_remember_user_toggled(self, checked: bool) -> None:
        """A password cannot be kept for a username that is not."""
        self.remember_password_check.setEnabled(checked)
        if not checked:
            self.remember_password_check.setChecked(False)

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
        self._record_choices(user.username, password)
        self.authenticated_user = user
        self.accept()

    def _record_choices(self, username: str, password: str) -> None:
        """Apply the two ticks to what is remembered about this account.

        Applied on a COMPLETED sign-in rather than the moment a box is
        clicked, so a tick cleared and restored while thinking about it costs
        nothing. Only a sign-in that succeeded says what was meant.
        """
        if self.remembered_login is None:
            return
        if not self.remember_user_check.isChecked():
            self.remembered_login.forget(username)
            return
        if self.remember_password_check.isChecked():
            self.remembered_login.remember_password(username, password)
        else:
            self.remembered_login.remember_username(username)
            self.remembered_login.forget_password(username)
        self.remembered_login.note_signed_in(username)

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

        dlg = CreateUserDialog(
            self.user_store,
            is_first_user=False,
            parent=self,
            remembered_login=self.remembered_login,
        )
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
        from clear_budget.ui.widgets.reset_password_dialog import ResetPasswordDialog

        ResetPasswordDialog(self.user_store, parent=self).exec()

    def _show_error(self, msg: str) -> None:
        self.error_label.setText(msg)
        self.error_label.setVisible(True)
