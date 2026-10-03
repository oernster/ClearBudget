"""Copying a SQLite database the application currently has OPEN.

A budget database is never idle while the app is running: a connection holds
it, with pages cached in memory and possibly a transaction in flight. Two
operations in the UI used a filesystem copy against exactly that file and
both were wrong for the same reason.

SAVE copied the live file out with `shutil.copy2`. A byte-for-byte copy of a
database mid-transaction is a copy of a file that no consistent state ever
matched, so the backup can be unreadable while looking the right size.

LOAD copied a chosen file back OVER the live one while the connection was
still open. Windows permits that, because SQLite opens with sharing flags
that allow it, so nothing fails at the time. The open connection then still
holds its own cached image of a file that has been replaced underneath it;
whatever it writes next is written against a database that is no longer
there. The user's data ends up destroyed by the act of loading it.

Both are fixed by never treating an open database as an ordinary file:

  * to copy one OUT, use SQLite's own online backup API, which takes a
    consistent snapshot with the connection live (`backup_open_database`);
  * to replace one, CLOSE it first and only then put the new file in place
    (`replace_closed_database`), which the composition root does because it
    is the only place that owns the connection's lifetime.

Both write to a temporary file beside the destination and rename it into
place, so an interrupted copy can never leave a half-written database where
a whole one used to be.

British spelling is used in comments.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

_TEMP_SUFFIX = ".partial"

# How long a snapshot waits for another connection's write lock to clear
# before refusing. Read at call time so a test can shorten it.
SNAPSHOT_BUSY_TIMEOUT_S = 5.0


class DatabaseCopyError(RuntimeError):
    """A copy or replace that could not complete; the message says why."""


def _temp_beside(dest: Path) -> Path:
    """A fresh scratch file on the SAME volume as ``dest``.

    The name is unique rather than derived from the destination. A fixed
    name has to be deleted before it can be reused, so a leftover that
    cannot be removed (another process still holds it) would fail every
    subsequent save; a unique name simply never collides.
    """
    handle, name = tempfile.mkstemp(
        dir=str(dest.parent), prefix=dest.name + ".", suffix=_TEMP_SUFFIX
    )
    os.close(handle)
    return Path(name)


def _discard(path: Path) -> None:
    """Remove a leftover scratch file, ignoring a failure to do so."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def backup_open_database(conn: sqlite3.Connection, dest: Path) -> None:
    """Write a consistent snapshot of the OPEN ``conn`` to ``dest``.

    Uses SQLite's online backup API rather than copying the file, so the
    result is a database as of one instant even though the source is live.

    Any write still in flight on ``conn`` is COMMITTED first, for two
    reasons learned the hard way. Backing up through a connection sitting on
    its own uncommitted write DEADLOCKS: the read waits on a transaction only
    the caller can end, so the application hangs rather than failing. And a
    save that silently dropped the edit the user had just made would be its
    own kind of data loss, so work in hand belongs in the backup.

    The snapshot is built in a scratch file beside the destination and only
    then renamed over it, so a failure part way through leaves an existing
    backup exactly as it was rather than truncated.
    """
    _backup_into(conn, dest, commit_first=True)


def _backup_into(conn: sqlite3.Connection, dest: Path, *, commit_first: bool) -> None:
    """Back ``conn`` up to a scratch file beside ``dest``, then rename it in.

    ``commit_first`` ends a write ``conn`` has in flight; a snapshot passes
    False because its own read transaction is what keeps it consistent.
    """
    temp = _temp_beside(dest)
    try:
        if commit_first and conn.in_transaction:
            conn.commit()
        target = sqlite3.connect(str(temp))
        try:
            conn.backup(target)
        finally:
            # sqlite3's context manager commits but never closes; on
            # Windows an open handle blocks the rename below.
            target.close()
        os.replace(temp, dest)
    except (OSError, sqlite3.Error) as exc:
        _discard(temp)
        raise DatabaseCopyError(str(exc)) from exc


def snapshot_database_file(source: Path, dest: Path) -> None:
    """Write a consistent snapshot of the database FILE ``source`` to ``dest``.

    For a database some other connection may hold open, when that connection
    is not ours to use: Back Up Everything copies every account's budget and
    the accounts store while the app holds at least two of them. A byte copy
    was measured taking a write still in progress into the backup as if it
    had been committed.

    A read transaction is opened FIRST (under a bounded busy timeout) and the
    backup runs inside it. Opening it is what makes the wait bounded: without
    it, SQLite's backup retries a locked source forever, which on the UI
    thread is a hang. With it, a file that stays locked (a writer part way
    through a large change) is refused with "database is locked" after
    `SNAPSHOT_BUSY_TIMEOUT_S`; an ordinary pending write does not lock
    readers out, so the snapshot simply holds the last committed state.
    """
    try:
        conn = sqlite3.connect(
            f"file:{source}?mode=ro",
            uri=True,
            timeout=SNAPSHOT_BUSY_TIMEOUT_S,
            isolation_level=None,
        )
    except sqlite3.Error as exc:
        raise DatabaseCopyError(str(exc)) from exc
    try:
        try:
            conn.execute("BEGIN")
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except sqlite3.Error as exc:
            raise DatabaseCopyError(str(exc)) from exc
        _backup_into(conn, dest, commit_first=False)
    finally:
        conn.close()


@dataclass(frozen=True, slots=True)
class KeptOriginal:
    """The database a replace displaced, held until the new one has opened.

    ``kept`` is None when there was nothing at ``dest`` to keep.
    """

    dest: Path
    kept: Path | None

    def restore(self) -> None:
        """Put the original back over whatever replaced it."""
        if self.kept is None:
            self.dest.unlink(missing_ok=True)
            return
        os.replace(self.kept, self.dest)

    def discard(self) -> None:
        """The replacement is good: let the original go."""
        if self.kept is not None:
            _discard(self.kept)


def replace_keeping_original(source: Path, dest: Path) -> KeptOriginal:
    """`replace_closed_database`, holding on to the database it displaces.

    Load validates the chosen file before this is called, yet a file can pass
    every check and still fail to open; measured, the budget it replaced was
    then simply gone. So the original is MOVED aside first (a rename, so it
    is never half-copied). The caller restores it if the new one does not
    open; once it has, the caller discards it. A failed copy puts it back at once.
    """
    kept = _move_aside(dest) if dest.exists() else None
    try:
        replace_closed_database(source, dest)
    except DatabaseCopyError:
        if kept is not None:
            os.replace(kept, dest)
        raise
    return KeptOriginal(dest=dest, kept=kept)


def _move_aside(dest: Path) -> Path:
    """Rename ``dest`` to a fresh scratch name beside it; return that name."""
    try:
        kept = _temp_beside(dest)
    except OSError as exc:
        raise DatabaseCopyError(str(exc)) from exc
    try:
        os.replace(dest, kept)
    except OSError as exc:
        _discard(kept)
        raise DatabaseCopyError(str(exc)) from exc
    return kept


def replace_closed_database(source: Path, dest: Path) -> None:
    """Put ``source`` in place as ``dest``, which must NOT be open.

    The caller closes the database first. That ordering is the whole point:
    replacing a file underneath a live connection is what corrupted user
    data; no amount of care inside this function can make it safe, so the
    responsibility sits with whoever owns the connection.

    The source is copied to a scratch file beside the destination and then
    renamed over it, so the destination is either the old database or the
    new one and never a partial write of either.
    """
    temp = _temp_beside(dest)
    try:
        with open(source, "rb") as src, open(temp, "wb") as dst:
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                dst.write(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(temp, dest)
    except OSError as exc:
        _discard(temp)
        raise DatabaseCopyError(str(exc)) from exc
