"""Nothing threatens a budget until the chosen file is known to be writable.

The Load flow's overwrite question says that every bill, income source, card,
override and setting is about to be permanently replaced. It is the right thing
to ask before a load and the wrong thing to ask about a file that is then
refused: picking the accounts store used to raise that threat, take a Yes, then
afterwards report that the file was never a budget. The user was asked to
accept losing everything for an operation that could not happen.

So every refusal comes first and the confirmation comes last, immediately
before the path is handed back. The order asserted here is the whole guard,
because each check is silent about the ones around it.

Save is held to the same order for the same reason, plus one refusal of its
own: a file belonging to another account is refused outright rather than
challenged. Loading someone else's budget is recoverable, which is why the
Load side offers it behind that account's password; saving OVER one replaces
their figures with yours and leaves nothing to recover from.

Source scan rather than a widget test: the suite is deliberately Qt-free (see
tests/conftest.py) and this flow is a chain of modal dialogs.
"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_FLOW = _ROOT / "clear_budget" / "ui" / "widgets" / "_save_load_flow.py"
_FUNCTION = "run_load_flow"
_SAVE = "run_save_flow"
_OWNERSHIP_REFUSAL = "_belongs_to_another_account("
# Save asks its own question, about its own file, so it has its own words.
_SAVE_CONFIRMATION = "Overwrite Save File?"

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


def _flow_source(name: str = _FUNCTION) -> str:
    tree = ast.parse(_FLOW.read_text(encoding="utf-8"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
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


class TestSaveRefusesAnotherAccountsBudget:
    """The mirror of the owner challenge, only stricter: no way past it."""

    def test_the_refusal_precedes_the_overwrite_confirmation(self):
        source = _flow_source(_SAVE)
        refusal_at = source.find(_OWNERSHIP_REFUSAL)
        confirmation_at = source.find(_SAVE_CONFIRMATION)
        assert refusal_at != -1, (
            f"{_SAVE} no longer asks whether the target belongs to another "
            "account, so a save can replace their budget with this one's"
        )
        assert confirmation_at != -1, f"{_SAVE} no longer confirms an overwrite"
        assert refusal_at < confirmation_at, (
            f"{_SAVE} asks about {_SAVE_CONFIRMATION} before finding out whose "
            "file it is, so the user is asked to accept a write that will then "
            "be refused"
        )

    def test_save_as_refuses_before_it_writes_or_remembers(self):
        source = _flow_source("run_save_as_flow")
        refusal_at = source.find(_OWNERSHIP_REFUSAL)
        assert refusal_at != -1, (
            "run_save_as_flow never asks whose file the chosen path is, so "
            "picking another account's budget by hand overwrites it"
        )
        for later in ("store_save_location(", "_copy_and_report("):
            assert refusal_at < source.find(later), (
                f"run_save_as_flow reaches {later} before the ownership "
                "refusal, so another account's budget is written or "
                "remembered before anyone asks whose it is"
            )
