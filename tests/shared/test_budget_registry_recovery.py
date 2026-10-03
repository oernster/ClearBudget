"""The budget list is a map; a lost or hostile map must not lose the budgets.

Measured: a list that does not parse fell back to one "Main budget", so every
named budget was still on disk with nothing in the app able to reach it; and
deleting the account then left those files behind. A list's slug also built a
path unchecked, so a hostile list could aim a delete outside the data folder.
Every test runs against the autouse scratch data directory (see conftest).
"""

from __future__ import annotations

import json
import os

import pytest

from clear_budget.shared import budget_registry as reg
from clear_budget.shared.config import LEGACY_BUDGET_SLUG, Config
from clear_budget.shared.db_ownership import stamp_owner
from tests.auth.backup_helpers import real_budget_db

_USER = "alice"


def _index_path():
    return Config.budgets_index_path(_USER)


def _write_index(text: str) -> None:
    path = _index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _db(slug: str):
    path = Config.for_user_budget(_USER, slug).db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    real_budget_db(path)
    return path


def _stamp(path, owner: str) -> None:
    import sqlite3

    conn = sqlite3.connect(str(path))
    try:
        stamp_owner(conn, owner)
    finally:
        conn.close()


class TestAnUnreadableListFindsTheBudgetsOnDisk:
    @pytest.mark.parametrize("text", ["{not json", "[]", '{"budgets": 3}'])
    def test_named_budgets_are_discovered(self, text):
        _db(LEGACY_BUDGET_SLUG)
        _db("holiday_fund")
        _write_index(text)
        index = reg.load_index(_USER)
        assert [r.slug for r in index.budgets] == [LEGACY_BUDGET_SLUG, "holiday_fund"]
        assert index.find("holiday_fund").name == "Holiday fund"
        assert index.active == LEGACY_BUDGET_SLUG

    def test_a_missing_list_discovers_them_too(self):
        _db("business")
        assert [r.slug for r in reg.load_index(_USER).budgets] == [
            LEGACY_BUDGET_SLUG,
            "business",
        ]

    def test_discovery_never_reaches_another_accounts_files(self):
        """`budget_alice__x` cannot be told from a user `alice  x` by name."""
        foreign = _db("bob_s")
        _stamp(foreign, "alice  bob s")
        own = _db("savings")
        _stamp(own, _USER)
        Config.for_user("alice2").db_path.write_bytes(b"")
        (foreign.parent / "budget_alice__a__b.db").write_bytes(b"")
        assert [r.slug for r in reg.load_index(_USER).budgets] == [
            LEGACY_BUDGET_SLUG,
            "savings",
        ]


class TestSlugsFromAListAreChecked:
    @pytest.mark.parametrize(
        "slug", ["../../escape", "..\\escape", "a/b", "Upper", "a__b", "_x", "x_"]
    )
    def test_an_unsafe_slug_is_dropped(self, slug):
        _write_index(
            json.dumps(
                {
                    "active": slug,
                    "budgets": [
                        {"slug": "", "name": "Main budget"},
                        {"slug": slug, "name": "Hostile"},
                    ],
                }
            )
        )
        index = reg.load_index(_USER)
        assert [r.slug for r in index.budgets] == [LEGACY_BUDGET_SLUG]
        assert reg.active_db_path(_USER).parent == Config.app_dir()

    def test_index_text_error_names_what_a_restore_must_refuse(self):
        assert "not valid JSON" in reg.index_text_error("{not json")
        assert "not a budget list" in reg.index_text_error("[]")
        hostile = '{"budgets": [{"slug": "../x", "name": "Out"}]}'
        assert "unsafe" in reg.index_text_error(hostile)
        assert reg.index_text_error("{}") is None
        assert reg.index_text_error('{"budgets": [{"slug": "ok"}, 3]}') is None


class TestDeletingAnAccountTakesEveryBudgetFile:
    def test_named_budgets_go_even_when_the_list_is_unreadable(self):
        legacy = _db(LEGACY_BUDGET_SLUG)
        holiday = _db("holiday_fund")
        (holiday.parent / (holiday.name + "-journal")).write_bytes(b"j")
        _write_index("{not json")
        reg.delete_all_budgets(_USER)
        assert not legacy.exists()
        assert not holiday.exists()
        assert not (holiday.parent / (holiday.name + "-journal")).exists()
        assert not _index_path().exists()

    def test_a_named_budget_the_list_forgot_still_goes(self):
        """A readable list that omits a file (hand-edited, half-written)."""
        reg.create_budget(_USER, "Business")
        forgotten = _db("holiday_fund")
        reg.delete_all_budgets(_USER)
        assert not forgotten.exists()

    def test_the_glob_stays_inside_this_accounts_prefix(self):
        _db("holiday_fund")
        neighbour = Config.for_user_budget("alicia", "holiday").db_path
        real_budget_db(neighbour)
        other_safe_name = neighbour.parent / "budget_alice__a__b.db"
        other_safe_name.write_bytes(b"")
        foreign = _db("bob_s")
        _stamp(foreign, "alice  bob s")
        reg.delete_all_budgets(_USER)
        assert neighbour.exists()
        assert other_safe_name.exists()
        assert foreign.exists()


class TestTheListIsWrittenWhole:
    def test_a_failed_write_leaves_the_previous_list(self, monkeypatch):
        reg.create_budget(_USER, "Business")
        before = _index_path().read_text(encoding="utf-8")

        def refuse(src, dst):
            raise OSError("disk full")

        # A scoped patch: `monkeypatch.undo()` would also lift the conftest
        # redirect and point every later path at the real data folder.
        with monkeypatch.context() as patch:
            patch.setattr(os, "replace", refuse)
            reg.create_budget(_USER, "Holiday")
        assert _index_path().read_text(encoding="utf-8") == before
        leftovers = [
            p.name
            for p in _index_path().parent.iterdir()
            if p.name.startswith(_index_path().name) and p != _index_path()
        ]
        assert leftovers == []
