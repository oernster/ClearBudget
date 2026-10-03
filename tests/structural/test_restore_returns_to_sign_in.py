"""After Restore Everything the sign-in screen appears, whatever happened.

The restore handler in main.py tears the session down (window hidden, budget
and accounts store closed) before it swaps any file, so the only place left
to go afterwards is sign-in. Measured: a backup with a bad CRC raised an
error the handler did not catch; nothing had changed on disk, yet the window
stayed hidden and no sign-in screen appeared, leaving an invisible process.

The damaged archive now arrives as a FullBackupError (tests/auth hold that).
This holds the backstop: the reopen and the return to sign-in sit in a
`finally`, so an error nobody anticipated still ends at the sign-in screen.
Source scan, because main.py is the Qt composition root and is excluded from
the coverage gate.
"""

from __future__ import annotations

import ast
from pathlib import Path

_MAIN = Path(__file__).resolve().parents[2] / "main.py"
_HANDLER = "_restore_everything"
_RETURN_TO_SIGN_IN = "_session_loop"
_REOPEN_STORE = "UserStore"


def _handler() -> ast.FunctionDef:
    tree = ast.parse(_MAIN.read_text(encoding="utf-8"))
    return next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == _HANDLER
    )


def _called_names(nodes: list[ast.stmt]) -> set[str]:
    names = set()
    for node in nodes:
        for call in ast.walk(node):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                names.add(call.func.id)
    return names


def test_the_return_to_sign_in_is_in_a_finally():
    tries = [node for node in ast.walk(_handler()) if isinstance(node, ast.Try)]
    assert tries, f"{_HANDLER} no longer guards the restore at all"
    finally_calls = set().union(*(_called_names(t.finalbody) for t in tries))
    assert _RETURN_TO_SIGN_IN in finally_calls, (
        f"{_HANDLER} returns to sign-in outside a finally, so an unexpected "
        "error after the session was torn down leaves no window at all"
    )
    assert _REOPEN_STORE in finally_calls, (
        f"{_HANDLER} reopens the accounts store outside a finally; sign-in "
        "would then run against a closed store"
    )
