"""Proving you own a budget before the app will open it.

The Load dialog opens on the directory every account's budget sits in, so the
file list shows other people's budgets by name. `shared.db_ownership` answers
whose file was chosen; this asks that account to prove itself.

The password required is the OWNER'S, never the loader's. Asking the loader for
their own password would be theatre: they know it, they would type it, then the
other account's budget would open anyway.

Lives in its own module rather than in `_save_load_flow`, which was four lines
under the 381 to 399 danger band that `tests/structural/test_loc_limits.py`
enforces when this was split out.
"""

from __future__ import annotations

from pathlib import Path

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
from clear_budget.shared.db_ownership import challenge_required
from clear_budget.ui import label_roles, ui_scale
from clear_budget.ui.widgets._login_styles import input_style

_DIALOG_WIDTH_PX = 420
_MARGIN_PX = 20
_SPACING_PX = 8


class OwnerChallengeDialog(QDialog):
    """Ask `owner` for their password before their budget is opened."""

    def __init__(self, owner: str, user_store: UserStore, parent=None) -> None:
        super().__init__(parent)
        self._owner = owner
        self._user_store = user_store
        self.setWindowTitle("This Budget Belongs to Another Account")
        self.setMinimumWidth(ui_scale.px(_DIALOG_WIDTH_PX))
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(ui_scale.px(_SPACING_PX))
        layout.setContentsMargins(*[ui_scale.px(_MARGIN_PX)] * 4)

        info = QLabel(
            f"The file you chose is {self._owner}'s budget, not yours.\n\n"
            f"Enter {self._owner}'s password to open it. Your own password "
            "will not do."
        )
        info.setWordWrap(True)
        info.setObjectName(label_roles.SUBTLE)
        layout.addWidget(info)
        layout.addSpacing(ui_scale.px(4))

        layout.addWidget(QLabel(f"Password for {self._owner}"))
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText(f"{self._owner}'s password")
        self._password.setStyleSheet(input_style())
        # No returnPressed connection here; "Open Budget" below is the
        # dialog's default button and a QLineEdit ignores Return so that it
        # reaches it. Connecting both is what showed the rejection warning
        # a second time: one press, two attempts, the modal in between
        # hiding the fact that the key was still travelling.
        layout.addWidget(self._password)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        unlock = QPushButton("Open Budget")
        unlock.setDefault(True)
        unlock.clicked.connect(self._attempt)
        row.addWidget(unlock)
        layout.addLayout(row)

    def _attempt(self) -> None:
        """Accept only when the OWNER's password verifies."""
        if self._user_store.verify_password(self._owner, self._password.text()):
            self.accept()
            return
        QMessageBox.warning(
            self,
            "Password Not Accepted",
            f"That is not {self._owner}'s password. The budget stays closed.",
        )
        self._password.clear()
        self._password.setFocus()


def owner_permits_load(
    parent,
    src_path: Path,
    current_username: str,
    user_store: UserStore,
) -> bool:
    """Whether `src_path` may be loaded by the account signed in now.

    True with no prompt when the file is unowned or already belongs to the
    signed-in account. Otherwise the owner is challenged; only their
    password opens it.
    """
    owner = challenge_required(
        src_path,
        current_username,
        [user.username for user in user_store.get_all_users()],
    )
    if owner is None:
        return True
    return OwnerChallengeDialog(owner, user_store, parent).exec() == QDialog.Accepted
