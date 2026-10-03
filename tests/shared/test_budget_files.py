"""Which data-directory files belong to an account; the quarantine folder."""

from __future__ import annotations

import sqlite3

import pytest

from clear_budget.shared import budget_files as bf
from clear_budget.shared.db_ownership import stamp_owner
from tests.auth.backup_helpers import real_budget_db


def _budget(app_dir, name, owner=None):
    path = app_dir / name
    real_budget_db(path)
    if owner is not None:
        conn = sqlite3.connect(str(path))
        try:
            stamp_owner(conn, owner)
        finally:
            conn.close()
    return path


class TestSlugShape:
    @pytest.mark.parametrize("slug", ["", "a", "holiday_fund", "x2_y3", "budget"])
    def test_safe(self, slug):
        assert bf.is_safe_slug(slug)

    @pytest.mark.parametrize(
        "slug", ["..", "a/b", "a\\b", "A", "a__b", "_a", "a_", "a.b", " a", 3]
    )
    def test_unsafe(self, slug):
        assert not bf.is_safe_slug(slug)


class TestBelongsTo:
    def test_by_name(self, tmp_path):
        assert bf.belongs_to(_budget(tmp_path, "budget_alice.db"), "Alice")
        assert bf.belongs_to(_budget(tmp_path, "budget_alice__trip.db"), "alice")
        assert bf.belongs_to(tmp_path / "budgets_alice.json", "alice")

    def test_not_by_name(self, tmp_path):
        assert not bf.belongs_to(_budget(tmp_path, "budget_alicia.db"), "alice")
        assert not bf.belongs_to(_budget(tmp_path, "budget_alice__a.b.db"), "alice")
        assert not bf.belongs_to(_budget(tmp_path, "budget_alice__a__b.db"), "alice")
        assert not bf.belongs_to(tmp_path / "budgets_alicia.json", "alice")
        assert not bf.belongs_to(tmp_path / "notes.txt", "alice")

    def test_a_stamp_for_someone_else_wins_over_the_name(self, tmp_path):
        path = _budget(tmp_path, "budget_alice__bob.db", owner="alice  bob")
        assert not bf.belongs_to(path, "alice")
        # The same name is `alice  bob`'s first budget, which the stamp confirms.
        assert bf.belongs_to(path, "alice  bob")

    def test_the_owners_stamp_agrees(self, tmp_path):
        path = _budget(tmp_path, "budget_alice.db", owner="alice")
        assert bf.belongs_to(path, "alice")


class TestEstateFiles:
    def test_budget_and_list_files_only(self, tmp_path):
        _budget(tmp_path, "budget_a.db")
        (tmp_path / "budgets_a.json").write_text("{}", encoding="utf-8")
        (tmp_path / "budget_a.db-journal").write_bytes(b"j")
        (tmp_path / "ui_settings.json").write_text("{}", encoding="utf-8")
        (tmp_path / "users.db").write_bytes(b"")
        names = sorted(p.name for p in bf.estate_files(tmp_path))
        assert names == ["budget_a.db", "budgets_a.json"]

    def test_with_sidecars_lists_only_what_exists(self, tmp_path):
        db = _budget(tmp_path, "budget_a.db")
        (tmp_path / "budget_a.db-wal").write_bytes(b"w")
        assert [p.name for p in bf.with_sidecars(db)] == [
            "budget_a.db",
            "budget_a.db-wal",
        ]
        assert [p.name for p in bf.with_sidecars(tmp_path / "budgets_a.json")] == []


class TestQuarantine:
    def test_moves_files_and_their_sidecars_never_deleting(self, tmp_path):
        db = _budget(tmp_path, "budget_carol.db")
        (tmp_path / "budget_carol.db-journal").write_bytes(b"j")
        listing = tmp_path / "budgets_carol.json"
        listing.write_text("{}", encoding="utf-8")
        folder, moved = bf.quarantine([db, listing], app_dir=tmp_path, reason="test")
        assert sorted(moved) == [
            "budget_carol.db",
            "budget_carol.db-journal",
            "budgets_carol.json",
        ]
        assert folder.parent == tmp_path / bf.QUARANTINE_DIR_NAME
        assert sorted(p.name for p in folder.iterdir()) == sorted(moved)
        assert not db.exists()

    def test_nothing_to_move_makes_no_folder(self, tmp_path):
        assert bf.quarantine([], app_dir=tmp_path, reason="test") == (None, [])
        assert not (tmp_path / bf.QUARANTINE_DIR_NAME).exists()

    def test_two_quarantines_never_collide(self, tmp_path):
        first, _ = bf.quarantine(
            [_budget(tmp_path, "budget_x.db")], app_dir=tmp_path, reason="r"
        )
        second, _ = bf.quarantine(
            [_budget(tmp_path, "budget_x.db")], app_dir=tmp_path, reason="r"
        )
        assert first != second
        assert (first / "budget_x.db").exists()
        assert (second / "budget_x.db").exists()
