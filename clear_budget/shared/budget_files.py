"""Which files in the data directory belong to which account.

Every account's budgets and its budget list sit side by side in ONE flat
directory, told apart only by name: `budget_<safe user>.db` for the first
budget, `budget_<safe user>__<slug>.db` for each named one and
`budgets_<safe user>.json` for the list. Three operations need to read those
names back: a restore deciding what belongs to no restored account, a new
account making sure it inherits nothing and an account delete finding every
budget even when the list cannot be read. This module is the one place that
reads them.

A name alone cannot always decide. A safe username may itself contain the
double underscore that separates a slug (`alice  bob` becomes `alice__bob`),
so `budget_alice__bob.db` is either alice's budget "bob" or the first budget
of `alice  bob`. Where a budget carries its owner stamp (see db_ownership) the
stamp settles it; an unstamped file is judged by its name.

Files that belong to no one are QUARANTINED: moved into a dated folder inside
the data directory, never deleted. The user's figures are never destroyed by a
guess about whose they are.
"""

from __future__ import annotations

import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from clear_budget.shared.db_ownership import owner_from_stamp, safe_username

# The folder, inside the data directory, that holds quarantined files.
QUARANTINE_DIR_NAME = "quarantine"

# The files SQLite keeps beside a database. Each travels with its database:
# left behind, a crash journal is played back over whatever file next takes
# that name.
SQLITE_SIDECAR_SUFFIXES = ("-journal", "-wal", "-shm")

# What separates the username from a named budget's slug in its file name.
# A slug can never contain it (see `is_safe_slug`); nor may a new account's
# safe username (see auth.user_store), else `budget_alice__bob.db` would be
# both alice's budget "Bob" and the first budget of `alice  bob`.
SLUG_SEPARATOR = "__"

BUDGET_DB_PATTERN = "budget_*.db"
BUDGET_LIST_PATTERN = "budgets_*.json"

_BUDGET_PREFIX = "budget_"
_LIST_PREFIX = "budgets_"
_DB_SUFFIX = ".db"
_LIST_SUFFIX = ".json"
_QUARANTINE_STAMP = "%Y%m%d-%H%M%S"

# The exact shape `budget_registry.safe_slug` produces: lower-case runs of
# letters and digits joined by single underscores. Anything else in a list
# file was not written by the app; a slug builds a path.
_SLUG_SHAPE = re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*")


def is_safe_slug(slug: object) -> bool:
    """Whether ``slug`` is the reserved empty slug or one the app could write."""
    if not isinstance(slug, str):
        return False
    return slug == "" or _SLUG_SHAPE.fullmatch(slug) is not None


def named_slug(path: Path, username: str) -> str | None:
    """The slug ``path``'s NAME gives it as one of ``username``'s named budgets.

    None when the name is not `budget_<safe user>__<slug>.db` with a slug the
    app could have written. Says nothing about the stamp; see `belongs_to`.
    """
    name = path.name.lower()
    prefix = f"{_BUDGET_PREFIX}{safe_username(username)}{SLUG_SEPARATOR}"
    if not (name.startswith(prefix) and name.endswith(_DB_SUFFIX)):
        return None
    slug = name[len(prefix) : -len(_DB_SUFFIX)]
    return slug if is_safe_slug(slug) and slug else None


def _named_as(path: Path, username: str) -> bool:
    """Whether the file NAME is one of ``username``'s budgets or their list."""
    safe = safe_username(username)
    name = path.name.lower()
    if name in (
        f"{_BUDGET_PREFIX}{safe}{_DB_SUFFIX}",
        f"{_LIST_PREFIX}{safe}{_LIST_SUFFIX}",
    ):
        return True
    return named_slug(path, username) is not None


def belongs_to(path: Path, username: str) -> bool:
    """Whether ``path`` is one of ``username``'s budget files or their list.

    The name must fit; for a database a stamp naming someone else overrides
    the name, which is what separates `alice`'s budget "bob" from the first
    budget of an account called `alice  bob`.
    """
    if not _named_as(path, username):
        return False
    if not path.name.lower().endswith(_DB_SUFFIX):
        return True
    stamped = owner_from_stamp(path)
    return stamped is None or safe_username(stamped) == safe_username(username)


def estate_files(app_dir: Path) -> list[Path]:
    """Every budget database and budget list directly in ``app_dir``."""
    found = [*app_dir.glob(BUDGET_DB_PATTERN), *app_dir.glob(BUDGET_LIST_PATTERN)]
    return sorted(p for p in found if p.is_file())


def with_sidecars(path: Path) -> list[Path]:
    """``path`` plus any SQLite sidecar beside it, as far as each exists."""
    candidates = [path]
    if path.name.lower().endswith(_DB_SUFFIX):
        candidates += [path.with_name(path.name + s) for s in SQLITE_SIDECAR_SUFFIXES]
    return [p for p in candidates if p.exists()]


def quarantine(
    paths: list[Path], *, app_dir: Path, reason: str
) -> tuple[Path | None, list[str]]:
    """Move ``paths`` and their sidecars into a fresh quarantine folder.

    Returns the folder and the names moved; (None, []) when there was nothing
    to move, so no empty folder is left to puzzle anyone. The folder is unique
    per call, so a second quarantine can never overwrite the first.
    """
    moving = [p for path in paths for p in with_sidecars(path)]
    if not moving:
        return None, []
    root = app_dir / QUARANTINE_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime(_QUARANTINE_STAMP)
    folder = Path(tempfile.mkdtemp(prefix=f"{stamp}-{reason}-", dir=str(root)))
    for path in moving:
        path.replace(folder / path.name)
    return folder, [p.name for p in moving]
