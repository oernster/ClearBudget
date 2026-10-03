"""A damaged or hostile backup is refused before a live file changes.

Each case here was measured taking real data with it: a duplicate entry that
overwrote the saved original of the budget it named; an accounts database of
the wrong shape that locked every account out; a budget whose data pages were
damaged behind an intact schema; a budget list that does not parse; a crash
journal left beside a live budget and played back over the restored one; a
damaged archive whose error escaped as something the caller did not expect.
"""

from __future__ import annotations

import shutil
import sqlite3
import warnings
import zipfile

import pytest

from clear_budget.auth import full_backup
from clear_budget.auth.full_backup import (
    USERS_DB_NAME,
    FullBackupError,
    create_full_backup,
    restore_full_backup,
    validate_full_backup,
)
from tests.auth.backup_helpers import (
    data_dir,
    marker_of,
    real_budget_db,
    rewrite_zip,
    set_marker,
    wreck_table_page,
)

_LIVE = "budget_oliver.db"


def _good_backup(tmp_path):
    app_dir = data_dir(tmp_path)
    set_marker(app_dir / _LIVE, "FROM-ZIP")
    package = tmp_path / "good.zip"
    create_full_backup(app_dir=app_dir, dest_path=package)
    set_marker(app_dir / _LIVE, "LIVE")
    return app_dir, package


def _snapshot(app_dir):
    return {p.name: p.read_bytes() for p in app_dir.iterdir() if p.is_file()}


class TestDuplicateEntries:
    @pytest.mark.parametrize("duplicate", [_LIVE, "BUDGET_OLIVER.db"])
    def test_a_duplicate_entry_is_refused_and_nothing_changes(
        self, tmp_path, duplicate
    ):
        app_dir, good = _good_backup(tmp_path)
        hostile = tmp_path / "hostile.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # zipfile warns on a duplicate name
            rewrite_zip(good, hostile, extra=((duplicate, b"x"),))
        before = _snapshot(app_dir)
        with pytest.raises(FullBackupError, match="more than once"):
            validate_full_backup(hostile)
        with pytest.raises(FullBackupError):
            restore_full_backup(package_path=hostile, app_dir=app_dir)
        assert _snapshot(app_dir) == before
        assert marker_of(app_dir / _LIVE) == "LIVE"

    def test_the_undo_puts_back_the_original_even_for_a_repeated_name(self, tmp_path):
        """Each file has its own aside path and the undo runs in reverse.

        A shared aside path let the second move overwrite the saved original;
        undoing in forward order then left the backup's copy in place.
        """
        app_dir = tmp_path / "data"
        staging = tmp_path / "staging"
        app_dir.mkdir()
        staging.mkdir()
        real_budget_db(app_dir / _LIVE, marker="LIVE")
        real_budget_db(staging / _LIVE, marker="FROM-ZIP")
        with pytest.raises(OSError):
            full_backup._replace_all([_LIVE, _LIVE], staging=staging, app_dir=app_dir)
        assert marker_of(app_dir / _LIVE) == "LIVE"


class TestTheAccountsDatabaseIsCheckedForShape:
    def test_a_users_table_of_the_wrong_shape_is_refused(self, tmp_path):
        app_dir, good = _good_backup(tmp_path)
        wrong = tmp_path / "wrong_users.db"
        conn = sqlite3.connect(str(wrong))
        conn.execute("CREATE TABLE users (x)")
        conn.commit()
        conn.close()
        hostile = tmp_path / "hostile.zip"
        rewrite_zip(good, hostile, replace={USERS_DB_NAME: wrong.read_bytes()})
        before = _snapshot(app_dir)
        with pytest.raises(FullBackupError, match="accounts database"):
            restore_full_backup(package_path=hostile, app_dir=app_dir)
        assert _snapshot(app_dir) == before

    def test_damaged_accounts_data_is_refused(self, tmp_path):
        app_dir, good = _good_backup(tmp_path)
        damaged = wreck_table_page(app_dir / USERS_DB_NAME, "users")
        hostile = tmp_path / "hostile.zip"
        rewrite_zip(good, hostile, replace={USERS_DB_NAME: damaged})
        before = _snapshot(app_dir)
        with pytest.raises(FullBackupError, match="accounts database"):
            restore_full_backup(package_path=hostile, app_dir=app_dir)
        assert _snapshot(app_dir) == before


class TestBudgetDataPagesAreRead:
    def test_a_budget_with_damaged_data_is_refused(self, tmp_path):
        app_dir, good = _good_backup(tmp_path)
        staged = tmp_path / "copy.db"
        with zipfile.ZipFile(good) as zf:
            staged.write_bytes(zf.read(_LIVE))
        hostile = tmp_path / "hostile.zip"
        rewrite_zip(
            good, hostile, replace={_LIVE: wreck_table_page(staged, "settings")}
        )
        before = _snapshot(app_dir)
        with pytest.raises(FullBackupError, match=_LIVE):
            restore_full_backup(package_path=hostile, app_dir=app_dir)
        assert _snapshot(app_dir) == before


class TestBudgetListsAreParsed:
    @pytest.mark.parametrize(
        "content",
        [
            b"{not json",
            b"[1, 2]",
            b'{"budgets": [{"slug": "../../escape", "name": "Out"}]}',
            b'{"budgets": [{"slug": "a\\\\b", "name": "Out"}]}',
        ],
    )
    def test_a_list_that_does_not_parse_or_escapes_is_refused(self, tmp_path, content):
        app_dir, good = _good_backup(tmp_path)
        hostile = tmp_path / "hostile.zip"
        rewrite_zip(good, hostile, replace={"budgets_oliver.json": content})
        before = _snapshot(app_dir)
        with pytest.raises(FullBackupError, match="budgets_oliver.json"):
            restore_full_backup(package_path=hostile, app_dir=app_dir)
        assert _snapshot(app_dir) == before


class TestCrashJournalsMoveWithTheirDatabase:
    _SIDECARS = ("-journal", "-wal", "-shm")

    def test_a_stale_journal_does_not_survive_beside_the_restored_file(self, tmp_path):
        app_dir, good = _good_backup(tmp_path)
        for suffix in self._SIDECARS:
            (app_dir / (_LIVE + suffix)).write_bytes(b"stale")
        restore_full_backup(package_path=good, app_dir=app_dir)
        for suffix in self._SIDECARS:
            assert not (app_dir / (_LIVE + suffix)).exists()
        assert marker_of(app_dir / _LIVE) == "FROM-ZIP"

    def test_a_failed_restore_puts_the_journals_back(self, tmp_path, monkeypatch):
        app_dir, good = _good_backup(tmp_path)
        for suffix in self._SIDECARS:
            (app_dir / (_LIVE + suffix)).write_bytes(b"live " + suffix.encode())
        before = _snapshot(app_dir)
        real_replace = type(app_dir).replace

        def flaky(self, target):
            if self.name == "budgets_oliver.json" and self.parent != app_dir:
                raise PermissionError("Access is denied")
            return real_replace(self, target)

        with monkeypatch.context() as patch:
            patch.setattr(type(app_dir), "replace", flaky)
            with pytest.raises(PermissionError):
                restore_full_backup(package_path=good, app_dir=app_dir)
        assert _snapshot(app_dir) == before

    def test_a_real_hot_journal_is_not_played_back_over_the_restore(self, tmp_path):
        """The measured case: a crashed writer's journal beside the live file."""
        app_dir, good = _good_backup(tmp_path)
        live = app_dir / _LIVE
        crashed = tmp_path / "crashed"
        crashed.mkdir()
        writer = sqlite3.connect(str(live))
        writer.execute("PRAGMA cache_size=1")
        writer.execute("BEGIN")
        writer.execute("UPDATE settings SET value='HALF' WHERE key='marker'")
        writer.execute("CREATE TABLE filler (x)")
        writer.executemany(
            "INSERT INTO filler VALUES (?)", [(b"z" * 3000,) for _ in range(200)]
        )
        # Copy the pair as a crash would leave it: database plus hot journal.
        shutil.copyfile(live, crashed / _LIVE)
        shutil.copyfile(app_dir / (_LIVE + "-journal"), crashed / "journal")
        writer.rollback()
        writer.close()
        shutil.copyfile(crashed / _LIVE, live)
        shutil.copyfile(crashed / "journal", app_dir / (_LIVE + "-journal"))

        restore_full_backup(package_path=good, app_dir=app_dir)
        assert marker_of(live) == "FROM-ZIP"


class TestADamagedArchiveIsAFullBackupError:
    def _damage(self, good, dest, compression):
        rewrite_zip(good, dest, compression=compression)
        with zipfile.ZipFile(dest) as zf:
            info = zf.getinfo(_LIVE)
        raw = bytearray(dest.read_bytes())
        header = 30 + len(info.filename.encode()) + len(info.extra)
        raw[info.header_offset + header + info.compress_size // 2] ^= 0xFF
        dest.write_bytes(bytes(raw))

    @pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
    def test_damaged_member_data_changes_nothing(self, tmp_path, compression):
        app_dir, good = _good_backup(tmp_path)
        hostile = tmp_path / "hostile.zip"
        self._damage(good, hostile, compression)
        validate_full_backup(hostile)  # the directory still reads
        before = _snapshot(app_dir)
        with pytest.raises(FullBackupError, match="damaged"):
            restore_full_backup(package_path=hostile, app_dir=app_dir)
        assert _snapshot(app_dir) == before
        assert not (app_dir / "_restore_staging").exists()
