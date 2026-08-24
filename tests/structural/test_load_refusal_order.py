"""Nothing threatens the budget until the chosen file is known to be loadable.

The Load flow's overwrite question says that every bill, income source, card,
override and setting is about to be permanently replaced. It is the right thing
to ask before a load and the wrong thing to ask about a file that is then
refused: picking the accounts store used to raise that threat, take a Yes, then
afterwards report that the file was never a budget. The user was asked to
accept losing everything for an operation that could not happen.

So every refusal comes first and the confirmation comes last, immediately
before the path is handed back. The order asserted here is the whole guard,
because each check is silent about the ones around it.

Source scan rather than a widget test: the suite is deliberately Qt-free (see
tests/conftest.py) and this flow is a chain of modal dialogs.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_FLOW = _ROOT / "clear_budget" / "ui" / "widgets" / "_save_load_flow.py"
_FUNCTION = "run_load_flow"

# In the order they must appear. Each refusal returns None; the last one is the
# only thing between the user and a replaced budget.
_REFUSALS = (
    "is_accounts_database(",
    "validate_db(",
    "owner_permits_load(",
)
# Matched WITHOUT its quotes: the source is compared after
# `ast.unparse`, which normalises double quotes to single ones.
_CONFIRMATION = "Overwrite Existing Data?"


def _flow_source() -> str:
    tree = ast.parse(_FLOW.read_text(encoding="utf-8"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == _FUNCTION
    )
    return ast.unparse(function)


class TestTheThreatComesLast:
    """The destructive question is the last gate, never the first."""

    def test_every_refusal_precedes_the_overwrite_confirmation(self):
        source = _flow_source()
        confirmation_at = source.find(_CONFIRMATION)
        assert confirmation_at != -1, (
            f"{_FUNCTION} no longer asks about {_CONFIRMATION}; either the guard "
            "has lost its subject or a load can now replace a budget unasked"
        )
        for refusal in _REFUSALS:
            refusal_at = source.find(refusal)
            assert refusal_at != -1, f"{_FUNCTION} no longer calls {refusal}"
            assert refusal_at < confirmation_at, (
                f"{_FUNCTION} asks about {_CONFIRMATION} before {refusal} has "
                "had a chance to refuse the file, so the user is warned their "
                "budget is about to be destroyed by a load that cannot happen"
            )
