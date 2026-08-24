"""Copying a database the application has open.

The regression these guard is not hypothetical. Loading a saved budget
replaced the live database file while its connection was still open; the
files that came out the other side were the right length and contained
nothing but zero bytes; two real budgets were destroyed by the act of
loading them.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from clear_budget.shared.db_copy import (
    DatabaseCopyError,
    backup_open_database,
    replace_closed_database,
)


def _make_db(path: Path, rows: int = 3) -> sqlite3.Connection:
    """A small real database, left OPEN, as the running app would hold it."""
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE bills (id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany(
        "INSERT INTO bills (name) VALUES (?)", [(f"bill {n}",) for n in range(rows)]
    )
    conn.commit()
    return conn


def _names(path: Path) -> list[str]:
    conn = sqlite3.connect(str(path))
    try:
        return [r[0] for r in conn.execute("SELECT name FROM bills ORDER BY id")]
    finally:
        conn.close()


class TestBackingUpAnOpenDatabase:
    def test_the_snapshot_is_readable_and_holds_the_rows(self, tmp_path):
        conn = _make_db(tmp_path / "live.db")
        try:
            dest = tmp_path / "backup.db"
            backup_open_database(conn, dest)
            assert _names(dest) == ["bill 0", "bill 1", "bill 2"]
        finally:
            conn.close()

    def test_the_snapshot_starts_with_the_sqlite_header(self, tmp_path):
        """The exact property the destroyed files lacked."""
        conn = _make_db(tmp_path / "live.db")
        try:
            dest = tmp_path / "backup.db"
            backup_open_database(conn, dest)
            assert dest.read_bytes()[:16] == b"SQLite format 3\x00"
            assert any(dest.read_bytes())
        finally:
            conn.close()

    def test_it_overwrites_an_existing_backup(self, tmp_path):
        conn = _make_db(tmp_path / "live.db")
        try:
            dest = tmp_path / "backup.db"
            dest.write_bytes(b"stale contents")
            backup_open_database(conn, dest)
            assert _names(dest) == ["bill 0", "bill 1", "bill 2"]
        finally:
            conn.close()

    def test_a_failure_leaves_the_existing_backup_untouched(self, tmp_path):
        conn = _make_db(tmp_path / "live.db")
        conn.close()  # a closed connection cannot be backed up
        dest = tmp_path / "backup.db"
        dest.write_bytes(b"the previous good backup")
        with pytest.raises(DatabaseCopyError):
            backup_open_database(conn, dest)
        assert dest.read_bytes() == b"the previous good backup"

    def test_a_failure_sweeps_its_scratch_file(self, tmp_path):
        conn = _make_db(tmp_path / "live.db")
        conn.close()
        dest = tmp_path / "backup.db"
        with pytest.raises(DatabaseCopyError):
            backup_open_database(conn, dest)
        assert list(tmp_path.glob("*.partial")) == []


class TestReplacingAClosedDatabase:
    def test_it_puts_the_source_in_place(self, tmp_path):
        source = tmp_path / "saved.db"
        conn = _make_db(source, rows=2)
        conn.close()
        dest = tmp_path / "live.db"
        live = _make_db(dest, rows=5)
        live.close()

        replace_closed_database(source, dest)

        assert _names(dest) == ["bill 0", "bill 1"]

    def test_the_replaced_file_is_a_real_database(self, tmp_path):
        source = tmp_path / "saved.db"
        _make_db(source).close()
        dest = tmp_path / "live.db"
        dest.write_bytes(b"\x00" * 4096)

        replace_closed_database(source, dest)

        assert dest.read_bytes()[:16] == b"SQLite format 3\x00"

    def test_a_missing_source_raises_rather_than_clearing_the_target(self, tmp_path):
        dest = tmp_path / "live.db"
        _make_db(dest).close()
        before = dest.read_bytes()

        with pytest.raises(DatabaseCopyError):
            replace_closed_database(tmp_path / "absent.db", dest)

        assert dest.read_bytes() == before

    def test_a_failure_sweeps_its_scratch_file(self, tmp_path):
        dest = tmp_path / "live.db"
        _make_db(dest).close()
        with pytest.raises(DatabaseCopyError):
            replace_closed_database(tmp_path / "absent.db", dest)
        assert list(tmp_path.glob("*.partial")) == []


class TestScratchFiles:
    def test_a_leftover_scratch_file_cannot_block_a_later_save(self, tmp_path):
        """The scratch name is unique, so a stranded leftover is irrelevant.

        A fixed scratch name had to be deleted before reuse, so one file
        another process still held would have failed every save from then on.
        """
        conn = _make_db(tmp_path / "live.db")
        try:
            (tmp_path / "backup.db.partial").write_bytes(b"stranded leftover")
            dest = tmp_path / "backup.db"
            backup_open_database(conn, dest)
            assert _names(dest) == ["bill 0", "bill 1", "bill 2"]
        finally:
            conn.close()

    def test_a_sweep_that_cannot_delete_still_reports_the_real_failure(
        self, tmp_path, monkeypatch
    ):
        """`_discard` swallows its OSError so the copy error is what surfaces."""
        conn = _make_db(tmp_path / "live.db")
        conn.close()  # forces the copy itself to fail

        def refuse(self, missing_ok=False):
            raise OSError("cannot remove the scratch file")

        monkeypatch.setattr(Path, "unlink", refuse)
        with pytest.raises(DatabaseCopyError):
            backup_open_database(conn, tmp_path / "backup.db")
