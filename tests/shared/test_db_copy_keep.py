"""Load keeps the budget it replaced until the new one has opened.

Measured: a damaged budget passed Load's checks, replaced the live file and
then failed to open; `main._reload_database` had no handler and no copy, so
the budget the user had was gone. Also here: the snapshot Back Up Everything
takes of a database file the app holds open.
"""

from __future__ import annotations

import sqlite3

import pytest

from clear_budget.shared import db_copy
from clear_budget.shared.db_copy import (
    DatabaseCopyError,
    replace_keeping_original,
    snapshot_database_file,
)
from tests.auth.backup_helpers import marker_of, real_budget_db


def _pair(tmp_path):
    live = tmp_path / "budget_a.db"
    chosen = tmp_path / "chosen.db"
    real_budget_db(live, marker="LIVE")
    real_budget_db(chosen, marker="CHOSEN")
    return live, chosen


def _beside(tmp_path):
    return sorted(p.name for p in tmp_path.iterdir())


class TestReplaceKeepingOriginal:
    def test_the_original_can_be_put_back(self, tmp_path):
        live, chosen = _pair(tmp_path)
        kept = replace_keeping_original(chosen, live)
        assert marker_of(live) == "CHOSEN"
        kept.restore()
        assert marker_of(live) == "LIVE"
        assert _beside(tmp_path) == ["budget_a.db", "chosen.db"]

    def test_the_original_is_dropped_once_the_new_one_is_good(self, tmp_path):
        live, chosen = _pair(tmp_path)
        replace_keeping_original(chosen, live).discard()
        assert marker_of(live) == "CHOSEN"
        assert _beside(tmp_path) == ["budget_a.db", "chosen.db"]

    def test_a_failed_copy_leaves_the_original_in_place(self, tmp_path):
        live, _ = _pair(tmp_path)
        with pytest.raises(DatabaseCopyError):
            replace_keeping_original(tmp_path / "absent.db", live)
        assert marker_of(live) == "LIVE"
        assert _beside(tmp_path) == ["budget_a.db", "chosen.db"]

    def test_a_failed_copy_onto_a_new_name_leaves_nothing(self, tmp_path):
        target = tmp_path / "budget_new.db"
        with pytest.raises(DatabaseCopyError):
            replace_keeping_original(tmp_path / "absent.db", target)
        assert not target.exists()

    def test_no_original_means_nothing_to_keep(self, tmp_path):
        _, chosen = _pair(tmp_path)
        target = tmp_path / "budget_new.db"
        kept = replace_keeping_original(chosen, target)
        kept.restore()
        assert not target.exists()
        replace_keeping_original(chosen, target).discard()
        assert marker_of(target) == "CHOSEN"

    def test_an_original_that_cannot_be_moved_aside_stays(self, tmp_path, monkeypatch):
        live, chosen = _pair(tmp_path)

        def refuse(src, dst):
            raise PermissionError("in use")

        with monkeypatch.context() as patch:
            patch.setattr(db_copy.os, "replace", refuse)
            with pytest.raises(DatabaseCopyError, match="in use"):
                replace_keeping_original(chosen, live)
        assert marker_of(live) == "LIVE"
        assert _beside(tmp_path) == ["budget_a.db", "chosen.db"]

    def test_no_room_for_the_aside_name_changes_nothing(self, tmp_path, monkeypatch):
        live, chosen = _pair(tmp_path)

        def refuse(**kwargs):
            raise OSError("no space")

        with monkeypatch.context() as patch:
            patch.setattr(db_copy.tempfile, "mkstemp", refuse)
            with pytest.raises(DatabaseCopyError, match="no space"):
                replace_keeping_original(chosen, live)
        assert marker_of(live) == "LIVE"


class TestSnapshotDatabaseFile:
    def test_copies_the_committed_state(self, tmp_path):
        source = tmp_path / "s.db"
        real_budget_db(source, marker="COMMITTED")
        dest = tmp_path / "d.db"
        snapshot_database_file(source, dest)
        assert marker_of(dest) == "COMMITTED"

    def test_a_failed_rename_leaves_no_partial_snapshot(self, tmp_path, monkeypatch):
        source = tmp_path / "s.db"
        real_budget_db(source)

        def refuse(src, dst):
            raise PermissionError("in use")

        with monkeypatch.context() as patch:
            patch.setattr(db_copy.os, "replace", refuse)
            with pytest.raises(DatabaseCopyError, match="in use"):
                snapshot_database_file(source, tmp_path / "d.db")
        assert sorted(p.name for p in tmp_path.iterdir()) == ["s.db"]

    def test_an_absent_source_is_a_copy_error(self, tmp_path):
        with pytest.raises(DatabaseCopyError):
            snapshot_database_file(tmp_path / "absent.db", tmp_path / "d.db")
        assert not (tmp_path / "d.db").exists()

    def test_a_locked_file_is_refused_after_the_wait(self, tmp_path, monkeypatch):
        monkeypatch.setattr(db_copy, "SNAPSHOT_BUSY_TIMEOUT_S", 0.1)
        source = tmp_path / "s.db"
        real_budget_db(source)
        writer = sqlite3.connect(str(source), isolation_level=None)
        writer.execute("BEGIN EXCLUSIVE")
        dest = tmp_path / "d.db"
        try:
            with pytest.raises(DatabaseCopyError, match="locked"):
                snapshot_database_file(source, dest)
        finally:
            writer.execute("ROLLBACK")
            writer.close()
        assert not dest.exists()
