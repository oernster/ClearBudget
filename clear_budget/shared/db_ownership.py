"""Who a budget database belongs to; proving it before opening one.

Every account's budget lives in ONE flat directory as `budget_<user>.db`, on
which the Load dialog opens. Loading validated the SCHEMA of the
chosen file and nothing else, so any signed-in user could pick the entry above
their own in the file list and open another account's budget, an administrator's
included. This module supplies the missing question: whose file is this?

Ownership is answered twice over, because neither answer alone is enough:

* the STAMP inside the database, written when the file is created. It travels
  with the file, so copying a budget somewhere else first does not launder it;
* the FILE NAME, which already encodes the owner through the same sanitiser
  that wrote it. This is what covers every database that existed before the
  stamp did, since those carry no stamp and never will unless reopened.

A file that answers neither is treated as unowned: an export or a backup the
loader keeps outside the app, which is theirs to load.

Read against the honesty line in the README: this is ACCESS CONTROL, not
encryption. It stops the app being used to read another account's budget. It
cannot stop someone with the file and any SQLite tool.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Iterable

# The settings row a budget's owner is recorded in, beside `currency`.
OWNER_SETTING_KEY = "owner"

_OWNER_QUERY = "SELECT value FROM settings WHERE key = ?"
_OWNER_WRITE = "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)"

# `budget_<safe username>.db`, else `budget_<safe username>__<slug>.db` for a
# named budget. The slug never contains an underscore run, which is what makes
# the double underscore a reliable separator (see Config.for_user_budget).
_DB_NAME = re.compile(r"^budget_(?P<safe>.+?)(?:__.+)?\.db$", re.IGNORECASE)


def safe_username(username: str) -> str:
    """The filesystem-safe form of `username`, as the path builder writes it.

    Mirrors `Config._safe_username`. Duplicated rather than imported because
    that one is private to the path builder; the two are pinned together by
    `tests/shared/test_db_ownership.py`, so a change to either fails the build.
    """
    return re.sub(r"[^a-zA-Z0-9_-]", "_", username).lower()


def stamp_owner(conn: sqlite3.Connection, username: str) -> None:
    """Record `username` as the owner of this budget, once and never again.

    INSERT OR IGNORE, so an existing stamp is never overwritten. Re-stamping
    would let a file be claimed simply by opening it, which is the whole thing
    this is here to prevent.
    """
    conn.execute(_OWNER_WRITE, (OWNER_SETTING_KEY, username))
    conn.commit()


def owner_from_stamp(path: Path) -> str | None:
    """The owner recorded INSIDE the database at `path`; None when unstamped.

    Returns None rather than raising for anything unreadable: a file that
    cannot be opened, has no settings table or holds no owner row. The caller
    falls back to the file name; a file that answers neither is unowned.
    """
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    # Closed explicitly rather than with `with`: sqlite3's context manager
    # commits and does NOT close, so the read handle outlived the call. On
    # Windows that handle is enough to make os.replace refuse the file, which
    # is how a restore was measured failing part way through.
    try:
        row = conn.execute(_OWNER_QUERY, (OWNER_SETTING_KEY,)).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    if row is None or not row[0]:
        return None
    return str(row[0])


def owner_from_filename(path: Path, known_usernames: Iterable[str]) -> str | None:
    """The owner the FILE NAME encodes, resolved against real accounts.

    The sanitiser is lossy, so a safe name can in principle match more than one
    account. An ambiguous name resolves to None rather than to a guess: naming
    the wrong owner would send the challenge to an account that cannot answer
    it, locking a file nobody can open.
    """
    match = _DB_NAME.match(path.name)
    if match is None:
        return None
    wanted = match.group("safe").lower()
    matches = [name for name in known_usernames if safe_username(name) == wanted]
    return matches[0] if len(matches) == 1 else None


def owner_of(path: Path, known_usernames: Iterable[str]) -> str | None:
    """Who the database at `path` belongs to; None when it belongs to nobody.

    The stamp wins, because it survives the file being moved or renamed. The
    file name is the fallback for a database written before stamping existed.
    """
    names = list(known_usernames)
    stamped = owner_from_stamp(path)
    if stamped is not None:
        return stamped
    return owner_from_filename(path, names)


def challenge_required(
    path: Path, current_username: str, known_usernames: Iterable[str]
) -> str | None:
    """The account that must prove itself before `path` may be loaded.

    None means load freely: either the file is unowned (an export or a backup
    kept outside the app) or it already belongs to the signed-in account.
    A username means exactly that account's password is required, never the
    loader's; asking the loader for their own password would be theatre, since
    they know it and would open the file anyway.
    """
    owner = owner_of(path, known_usernames)
    if owner is None or owner == current_username:
        return None
    return owner
