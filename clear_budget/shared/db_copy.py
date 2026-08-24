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
from pathlib import Path

_TEMP_SUFFIX = ".partial"


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

    The snapshot is built in a scratch file beside the destination and only
    then renamed over it, so a failure part way through leaves an existing
    backup exactly as it was rather than truncated.
    """
    temp = _temp_beside(dest)
    try:
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
