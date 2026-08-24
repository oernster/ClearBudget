"""A budget survives being closed and opened again. Every time. For good.

This is the end-to-end guard for the failure that cost two real budgets and
an entire evening: data that was present in a running session was gone
or unreadable at the next launch. Each way that happened is pinned here as
BEHAVIOUR rather than as a source scan, so no future refactor can reintroduce
it while still looking correct.

Three distinct routes destroyed or lost a budget:

  * Load replaced the live database file while its connection was still open,
    leaving a file of the right length containing nothing but zero bytes;
  * Save copied an open, possibly mid-transaction database byte for byte, so
    the backup it produced could not be opened;
  * an unreadable budget failed silently at sign-in, so the app showed
    nothing at all and the loss was invisible until far too late.

The session lifecycle is driven through the application's own
session-database helper, so these exercise the real path a sign-in takes
rather than a re-implementation of it.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from clear_budget.infrastructure.sqlite.session_database import (
    open_user_database,
)
from clear_budget.shared.config import Config
from clear_budget.shared.db_copy import backup_open_database, replace_closed_database

_USER = "oliver"

# A backup of a scratch database is instant; anything near this is a block.
_DEADLOCK_SECONDS = 10.0


def _counts(db_path) -> dict[str, int]:
    """Row counts for the tables a user would notice losing."""
    conn = sqlite3.connect(str(db_path))
    try:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("bills", "income_sources", "credit_cards", "settings")
        }
    finally:
        conn.close()


def _populate(database, *, bills: int) -> None:
    """Put recognisable data in, through the app's own open connection."""
    conn = database.conn
    conn.executemany(
        "INSERT INTO bills (name, amount_pence, category, bill_type, day_of_month,"
        " start_year, start_month, payment_method_id)"
        " VALUES (?, ?, 'utilities', 'monthly', 1, 2026, 1, 1)",
        [(f"bill {n}", 1000 + n) for n in range(bills)],
    )
    conn.execute(
        "INSERT INTO income_sources (name, amount_pence, is_reliable)"
        " VALUES ('salary', 200000, 1)"
    )
    conn.commit()


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """A scratch data directory the composition root will resolve to."""
    monkeypatch.setenv("CLEARBUDGET_HOME", str(tmp_path))
    return tmp_path


class TestAnOpenedBudgetSurvivesTheNextLaunch:
    def test_every_row_is_still_there_after_close_and_reopen(self, home):
        database = open_user_database(_USER)
        _populate(database, bills=7)
        path = database.db_path
        before = _counts(path)
        database.close()

        reopened = open_user_database(_USER)
        try:
            assert _counts(reopened.db_path) == before
            assert before["bills"] == 7
        finally:
            reopened.close()

    def test_reopening_never_rewrites_the_file(self, home):
        """Opening adopts an existing budget; it must not recreate one."""
        database = open_user_database(_USER)
        _populate(database, bills=3)
        path = database.db_path
        database.close()
        untouched = path.read_bytes()

        reopened = open_user_database(_USER)
        reopened.close()

        assert path.read_bytes() == untouched

    def test_a_budget_dropped_in_by_hand_is_adopted_whole(self, home):
        """Copying a database in while the app is closed is a supported route."""
        seed = open_user_database(_USER)
        _populate(seed, bills=11)
        seed.close()
        carried = home / "carried_elsewhere.db"
        carried.write_bytes(Config.for_user(_USER).db_path.read_bytes())
        Config.for_user(_USER).db_path.unlink()

        # As the user does it: app closed, file put in place, app opened.
        Config.for_user(_USER).db_path.write_bytes(carried.read_bytes())
        opened = open_user_database(_USER)
        try:
            assert _counts(opened.db_path)["bills"] == 11
        finally:
            opened.close()


class TestLoadingABudgetDoesNotDestroyIt:
    """The exact sequence that produced 143360 bytes of zeros."""

    def test_the_load_ordering_keeps_every_row_after_a_restart(self, home):
        saved = home / "saved_budget.db"
        source = open_user_database(_USER)
        _populate(source, bills=9)
        backup_open_database(source.conn, saved)
        source.close()

        # A different session, holding a different budget.
        live = open_user_database(_USER)
        _populate(live, bills=2)
        target = live.db_path

        # What the composition root does: CLOSE, replace, reopen.
        live.close()
        replace_closed_database(saved, target)

        reopened = open_user_database(_USER)
        try:
            assert _counts(reopened.db_path)["bills"] == 9
        finally:
            reopened.close()

        # And it is still there at the launch after that one.
        again = open_user_database(_USER)
        try:
            assert _counts(again.db_path)["bills"] == 9
        finally:
            again.close()

    def test_the_loaded_file_is_a_real_database_and_not_zeros(self, home):
        saved = home / "saved_budget.db"
        source = open_user_database(_USER)
        _populate(source, bills=4)
        backup_open_database(source.conn, saved)
        target = source.db_path
        source.close()

        replace_closed_database(saved, target)

        raw = target.read_bytes()
        assert raw[:16] == b"SQLite format 3\x00"
        assert any(raw), "the live database is entirely zero bytes"


class TestSavingAnOpenBudgetProducesAReadableBackup:
    def test_a_backup_taken_mid_transaction_can_still_be_opened(self, home):
        database = open_user_database(_USER)
        _populate(database, bills=5)
        # Uncommitted work in flight, exactly as a real session would have.
        database.conn.execute(
            "INSERT INTO bills (name, amount_pence, category, bill_type,"
            " day_of_month, start_year, start_month, payment_method_id)"
            " VALUES ('in flight', 999, 'utilities', 'monthly', 1, 2026, 1, 1)"
        )
        dest = home / "backup.db"

        backup_open_database(database.conn, dest)
        database.close()

        assert dest.read_bytes()[:16] == b"SQLite format 3\x00"
        # SIX, not five: the in-flight row is committed before the
        # snapshot. A save that silently dropped the edit the user just
        # made would be its own kind of data loss, so work in hand is in.
        assert _counts(dest)["bills"] == 6


class TestAnUnreadableBudgetIsReportedRatherThanSilent:
    def test_opening_a_damaged_budget_raises_so_the_ui_can_say_so(self, home):
        """It used to escape a Qt slot and show the user nothing whatsoever."""
        database = open_user_database(_USER)
        path = database.db_path
        database.close()
        path.write_bytes(b"\x00" * 143360)  # the exact damage seen in the wild

        with pytest.raises(sqlite3.DatabaseError):
            open_user_database(_USER)


_DEADLOCK_PROBE = """
import sqlite3, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from clear_budget.shared.db_copy import backup_open_database

conn = sqlite3.connect(sys.argv[2])
conn.execute("CREATE TABLE IF NOT EXISTS bills (id INTEGER PRIMARY KEY, name TEXT)")
conn.commit()
conn.execute("INSERT INTO bills (name) VALUES ('in flight')")
assert conn.in_transaction, "probe needs an open write transaction"
backup_open_database(conn, Path(sys.argv[3]))
print("COMPLETED")
"""


def test_a_backup_with_a_write_in_flight_cannot_deadlock(tmp_path):
    """The hang that leaves a process alive and the app unlaunchable.

    `conn.backup()` reads the source THROUGH SQLite; a connection sitting
    on its own uncommitted write blocks that read indefinitely. It does not
    raise, it waits, so the window stops responding and the process never
    exits. That process keeps the single-instance mutex, so every later
    launch is refused as "already running" and the application cannot be
    started at all until the stuck process is killed by hand.

    This runs in a SUBPROCESS with a deadline. A deadlock has no exception to
    catch, so elapsed time is the only honest assertion; a separate process is
    what lets the guard FAIL rather than hang the suite alongside the code it
    is testing. A sqlite3 connection is bound to its creating thread, so a
    worker thread is not an option here.
    """
    repo_root = str(Path(__file__).resolve().parents[2])
    result = None
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                _DEADLOCK_PROBE,
                repo_root,
                str(tmp_path / "live.db"),
                str(tmp_path / "snapshot.db"),
            ],
            capture_output=True,
            text=True,
            timeout=_DEADLOCK_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError(
            f"backing up an open database did not finish within "
            f"{_DEADLOCK_SECONDS}s, so it blocked on the connection's own "
            "open transaction. In the application that is a frozen window and "
            "a process that never exits, holding the single-instance lock so "
            "the app can never be launched again."
        )
    assert result.returncode == 0, result.stderr
    assert "COMPLETED" in result.stdout
