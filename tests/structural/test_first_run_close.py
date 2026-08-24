"""The first-run wizard must keep its close button.

With no users in the database the wizard is the ONLY window the app shows,
so stripping its close button left the app unkillable from mouse and
keyboard alike. The no-close flags belong to RecoveryCodeDialog alone (the
one-time code must be acknowledged, since closing it unread loses the code
forever). Asserted by source scan because the suite is Qt-free; the runtime
behaviour (flag present, close rejects, main quits on reject) is verified
by an offscreen probe.
"""

import ast
from pathlib import Path

_DIALOG = (
    Path(__file__).resolve().parents[2]
    / "clear_budget"
    / "ui"
    / "widgets"
    / "create_user_dialog.py"
)

_FLAGS_NAME = "_NO_CLOSE_FLAGS"


def _class_source(name: str) -> str:
    tree = ast.parse(_DIALOG.read_text(encoding="utf-8"))
    node = next(
        n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == name
    )
    return ast.dump(node)


def test_the_create_user_wizard_never_strips_its_close_button() -> None:
    assert _FLAGS_NAME not in _class_source("CreateUserDialog"), (
        "CreateUserDialog applies the no-close window flags again; with no "
        "users the wizard is the only window, so the app cannot be exited"
    )


def test_the_recovery_code_dialog_still_requires_acknowledgement() -> None:
    assert _FLAGS_NAME in _class_source("RecoveryCodeDialog"), (
        "RecoveryCodeDialog lost its no-close flags; the one-time code could "
        "be dismissed unread and lost forever"
    )
