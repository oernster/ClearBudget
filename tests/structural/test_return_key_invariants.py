"""One Return press runs a dialog's submit ONCE.

A `QLineEdit` does not consume the Return key. It emits `returnPressed` and
then IGNORES the event, precisely so the key carries on to the dialog's default
button. So a dialog that connects `returnPressed` to the same slot its default
button already calls has two mechanisms for one press; one press then runs
the slot twice.

That stayed invisible for as long as the second run was harmless: a dialog that
accepts on the first run is closed before the key arrives; an inline error
label simply gets written twice with the same words. It became visible the
moment a submit answered failure with a MODAL: entering the wrong password on
the owner challenge showed "Password Not Accepted"; dismissing it showed it
again, because the key had been waiting behind the modal the whole time. All
four dialogs that connected `returnPressed` were double-running; only one of
them showed it (measured on all four, before and after).

The rule is one mechanism: the default button. Asserted by source scan because
the suite is deliberately Qt-free (see tests/conftest.py); the counts behind it
came from an offscreen probe.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCANNED = (
    _ROOT / "clear_budget" / "ui",
    _ROOT / "installer" / "ui",
)

_RETURN_PRESSED = "returnPressed"
_CLICKED = "clicked"


def _connected_slots(tree: ast.Module, signal: str) -> dict[str, int]:
    """Source text of every slot connected to `signal`, to its first line."""
    found: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        connect = node.func
        if not isinstance(connect, ast.Attribute) or connect.attr != "connect":
            continue
        emitter = connect.value
        if not isinstance(emitter, ast.Attribute) or emitter.attr != signal:
            continue
        found.setdefault(ast.unparse(node.args[0]), node.lineno)
    return found


def _modules() -> list[Path]:
    return [
        path
        for directory in _SCANNED
        if directory.exists()
        for path in sorted(directory.rglob("*.py"))
    ]


class TestReturnSubmitsOnce:
    """A submit is reachable by Return through ONE route, never two."""

    def test_no_slot_is_both_a_return_handler_and_a_button_handler(self):
        offenders = []
        for path in _modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            on_return = _connected_slots(tree, _RETURN_PRESSED)
            on_click = _connected_slots(tree, _CLICKED)
            for slot, lineno in sorted(on_return.items()):
                if slot in on_click:
                    offenders.append(
                        f"{path.relative_to(_ROOT)}:{lineno}: {slot} answers both "
                        f"{_RETURN_PRESSED} and {_CLICKED}"
                    )

        assert not offenders, (
            "One Return press would run these submits TWICE: a QLineEdit "
            "ignores Return after emitting, so the key reaches the button "
            "as well. Drop the "
            f"{_RETURN_PRESSED} connection and let the default button own it "
            "(`setDefault(True)` on the submit, `setAutoDefault(False)` on "
            "Cancel).\n" + "\n".join(offenders)
        )
