"""A live database is closed BEFORE it is replaced, only ever in main.py.

This is a source scan rather than a behaviour test because the ordering it
protects lives in a Qt slot inside the composition root; getting it wrong
is also silent: replacing an open database succeeds on Windows and the
damage only surfaces at the next launch.

The bug this pins: `run_load_flow` used to copy the chosen file over the live
database while the connection was still open. Nothing failed at the time; the
connection carried on writing against a file that had been swapped out and
what survived was the right length and entirely zero bytes. Two real budgets
were destroyed by the act of loading them.
"""

from __future__ import annotations

import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_UI_ROOT = _PROJECT_ROOT / "clear_budget" / "ui"
# The call that puts a loaded file in place of the live budget. It keeps the
# budget it displaces until the loaded one has opened (see db_copy).
_REPLACE_CALL = "replace_keeping_original("


def _main_source() -> str:
    return (_PROJECT_ROOT / "main.py").read_text(encoding="utf-8")


class TestTheCompositionRootClosesFirst:
    def test_main_closes_the_active_database_before_replacing_it(self):
        source = _main_source()
        replace_at = source.find(_REPLACE_CALL)
        assert replace_at != -1, "main.py no longer replaces the database at all"

        window = source[:replace_at]
        close_at = window.rfind("_active_database[0].close()")
        assert close_at != -1, (
            "main.py replaces the live budget with no preceding close of "
            "the active database. Replacing a database underneath its own open "
            "connection is what destroyed two real budgets."
        )

    def test_the_clear_follows_the_close_before_any_replace(self):
        """A closed handle left in the list would be reopened as if live."""
        source = _main_source()
        replace_at = source.find(_REPLACE_CALL)
        window = source[:replace_at]
        assert window.rfind("_active_database.clear()") > window.rfind(
            "_active_database[0].close()"
        )

    def test_a_kept_budget_is_put_back_only_after_the_failed_one_closes(self):
        """Putting the original back is a replace too; the same order holds.

        The loaded file has just failed to open, possibly after a connection
        to it was made, so that connection is closed first.
        """
        source = _main_source()
        failed_at = source.find(
            "except sqlite3.DatabaseError as exc:\n            if kept"
        )
        restore_at = source.find("kept.restore()")
        assert -1 < failed_at < restore_at, "main.py no longer restores a kept budget"
        between = source[failed_at:restore_at]
        assert between.find("_active_database[0].close()") != -1
        assert between.rfind("_active_database.clear()") > between.rfind(
            "_active_database[0].close()"
        )


class TestTheUiNeverReplacesADatabase:
    """The UI layer may CHOOSE a file; only the composition root swaps one in."""

    def test_no_ui_module_copies_a_file_over_the_live_database(self):
        pattern = re.compile(r"shutil\.(copy2?|copyfile)\s*\(")
        offenders = [
            str(path.relative_to(_PROJECT_ROOT))
            for path in _UI_ROOT.rglob("*.py")
            if "__pycache__" not in path.parts
            and pattern.search(path.read_text(encoding="utf-8"))
        ]
        assert not offenders, (
            "A UI module filesystem-copies a database. Saving must go through "
            "SQLite's backup API and replacing must happen in main.py after "
            "the connection is closed:\n" + "\n".join(offenders)
        )
