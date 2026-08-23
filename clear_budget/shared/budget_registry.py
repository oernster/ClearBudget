"""The set of named budgets a user owns, plus which one is active.

A budget is one SQLite file. Before named budgets a user had exactly one, at
`budget_<user>.db`, chosen by nothing because there was nothing to choose. This
module is the record of the several a user may now own: their slugs, their
display names and which is currently open.

The record is a JSON sidecar per user, written the same best-effort way as the
UI's `save_location`. Two rules keep it safe against the installs that predate
it:

* The FIRST budget keeps the reserved empty slug, so its file is the very
  `budget_<user>.db` that already exists. Naming budgets moves no data.
* An absent, empty or unreadable sidecar SYNTHESISES that one record rather
  than failing. A user who has never opened this dialog has one budget called
  "Main budget" and cannot tell the sidecar is missing.

So the migration is that there is no migration: the sidecar is written the
first time a second budget is created; not before.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

from clear_budget.shared.config import LEGACY_BUDGET_SLUG, Config

# What the first budget is called when the sidecar has never been written.
DEFAULT_BUDGET_NAME = "Main budget"

# Fallback slug for a name with no slug-able characters at all (say "£££").
_FALLBACK_SLUG = "budget"

_VERSION_KEY = "version"
_ACTIVE_KEY = "active"
_BUDGETS_KEY = "budgets"
_SLUG_KEY = "slug"
_NAME_KEY = "name"
_FORMAT_VERSION = 1

# The sidecar files SQLite writes beside a database. Deleting a budget has to
# take these too; otherwise a stale WAL outlives the database it belonged to.
_DB_SIDECAR_SUFFIXES = ("", "-wal", "-shm", "-journal")


class BudgetRegistryError(Exception):
    """A budget operation that cannot be honoured, with a user-facing message."""


@dataclass(frozen=True, slots=True)
class BudgetRecord:
    """One named budget: its file slug and the name the user sees."""

    slug: str
    name: str


@dataclass(frozen=True, slots=True)
class BudgetIndex:
    """Every budget a user owns, plus the slug of the active one."""

    active: str
    budgets: tuple[BudgetRecord, ...]

    def find(self, slug: str) -> BudgetRecord | None:
        """Return the record with `slug`; None when there is none."""
        for record in self.budgets:
            if record.slug == slug:
                return record
        return None

    def active_record(self) -> BudgetRecord:
        """Return the active budget, falling back to the first one.

        The fallback matters: a sidecar naming an active slug that no longer
        exists (hand-edited or half-written by a crash) must still open
        something rather than leave the user with no budget at all.
        """
        return self.find(self.active) or self.budgets[0]


def _default_index() -> BudgetIndex:
    """The synthesised record for a user whose sidecar has never been written."""
    return BudgetIndex(
        active=LEGACY_BUDGET_SLUG,
        budgets=(BudgetRecord(LEGACY_BUDGET_SLUG, DEFAULT_BUDGET_NAME),),
    )


def safe_slug(name: str) -> str:
    """Return a filesystem-safe slug for `name`.

    Runs of anything that is not alphanumeric collapse to ONE underscore and
    the ends are trimmed, so a slug can never contain the double underscore
    that separates it from the username in the filename.
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return slug or _FALLBACK_SLUG


def _unique_slug(index: BudgetIndex, name: str) -> str:
    """A slug for `name` that no existing budget already uses."""
    base = safe_slug(name)
    taken = {record.slug for record in index.budgets}
    if base not in taken:
        return base
    suffix = 2
    while f"{base}_{suffix}" in taken:
        suffix += 1
    return f"{base}_{suffix}"


def _parse_record(raw: object) -> BudgetRecord | None:
    """Return the record `raw` describes; None when it is not a usable one."""
    if not isinstance(raw, dict):
        return None
    slug = raw.get(_SLUG_KEY)
    name = raw.get(_NAME_KEY)
    if not isinstance(slug, str) or not isinstance(name, str) or not name.strip():
        return None
    return BudgetRecord(slug, name.strip())


def load_index(username: str) -> BudgetIndex:
    """Return `username`'s budgets, synthesising the default when unreadable.

    Every failure mode collapses to the same answer, the single legacy budget:
    no file, unparseable JSON, the wrong shape, a budget list holding
    nothing usable. The user's data is the database files; this sidecar is only
    the map to them, so a lost map means "the one budget I can prove exists"
    rather than an error the user cannot act on.
    """
    try:
        data = json.loads(Config.budgets_index_path(username).read_text("utf-8"))
    except (OSError, ValueError):
        return _default_index()
    if not isinstance(data, dict):
        return _default_index()
    raw_budgets = data.get(_BUDGETS_KEY)
    if not isinstance(raw_budgets, list):
        return _default_index()
    records = tuple(
        record for record in map(_parse_record, raw_budgets) if record is not None
    )
    if not records:
        return _default_index()
    active = data.get(_ACTIVE_KEY)
    return BudgetIndex(
        active=active if isinstance(active, str) else records[0].slug,
        budgets=records,
    )


def store_index(username: str, index: BudgetIndex) -> None:
    """Persist `index` for `username`, best-effort.

    A write failure is swallowed for the same reason `save_location` swallows
    one: the databases themselves are untouched, so the only cost is that the
    session's choice of active budget is not remembered next launch.
    """
    path = Config.budgets_index_path(username)
    payload = {
        _VERSION_KEY: _FORMAT_VERSION,
        _ACTIVE_KEY: index.active,
        _BUDGETS_KEY: [
            {_SLUG_KEY: record.slug, _NAME_KEY: record.name} for record in index.budgets
        ],
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def active_db_path(username: str) -> Path:
    """The database file of `username`'s currently active budget."""
    record = load_index(username).active_record()
    return Config.for_user_budget(username, record.slug).db_path


def set_active(username: str, slug: str) -> None:
    """Make `slug` the active budget, if it is one this user owns."""
    index = load_index(username)
    if index.find(slug) is None:
        raise BudgetRegistryError("That budget no longer exists.")
    store_index(username, replace(index, active=slug))


def create_budget(username: str, name: str) -> BudgetRecord:
    """Register a new EMPTY budget called `name` and make it active.

    The database file is not created here. The caller opens the returned
    budget through the normal path, which creates and migrates the schema
    exactly as it does for a first-run user, so a new budget and a brand new
    account produce byte-identical databases.
    """
    clean = name.strip()
    if not clean:
        raise BudgetRegistryError("A budget needs a name.")
    index = load_index(username)
    if any(record.name.lower() == clean.lower() for record in index.budgets):
        raise BudgetRegistryError(f"You already have a budget called '{clean}'.")
    record = BudgetRecord(_unique_slug(index, clean), clean)
    store_index(
        username,
        BudgetIndex(active=record.slug, budgets=index.budgets + (record,)),
    )
    return record


def rename_budget(username: str, slug: str, name: str) -> None:
    """Rename one budget. The slug never changes, so neither does the file."""
    clean = name.strip()
    if not clean:
        raise BudgetRegistryError("A budget needs a name.")
    index = load_index(username)
    if index.find(slug) is None:
        raise BudgetRegistryError("That budget no longer exists.")
    clash = any(
        record.name.lower() == clean.lower() and record.slug != slug
        for record in index.budgets
    )
    if clash:
        raise BudgetRegistryError(f"You already have a budget called '{clean}'.")
    renamed = tuple(
        replace(record, name=clean) if record.slug == slug else record
        for record in index.budgets
    )
    store_index(username, replace(index, budgets=renamed))


def delete_budget(username: str, slug: str) -> str:
    """Delete one budget and its database. Returns the now-active slug.

    The LAST budget can never be deleted. Allowing it would leave the account
    with nothing to open, which the rest of the app has no state for; wiping a
    budget you want emptied is what Load and a fresh budget are for.

    The caller must not pass the budget the session currently has OPEN:
    Windows refuses to unlink a file SQLite still holds, so the registry would
    be updated and the database left behind. The dialog enforces that by
    disabling Delete on the active budget.
    """
    index = load_index(username)
    if index.find(slug) is None:
        raise BudgetRegistryError("That budget no longer exists.")
    if len(index.budgets) == 1:
        raise BudgetRegistryError(
            "This is your only budget, so it cannot be deleted.\n\n"
            "Create another one first, then delete this."
        )
    remaining = tuple(record for record in index.budgets if record.slug != slug)
    active = index.active if index.active != slug else remaining[0].slug
    store_index(username, BudgetIndex(active=active, budgets=remaining))
    delete_db_files(Config.for_user_budget(username, slug).db_path)
    return active


def delete_db_files(db_path: Path) -> None:
    """Delete a database and the WAL/SHM/journal files SQLite keeps beside it."""
    for suffix in _DB_SIDECAR_SUFFIXES:
        path = db_path.with_name(db_path.name + suffix)
        if path.exists():
            path.unlink()


def delete_all_budgets(username: str) -> None:
    """Delete every budget database `username` owns, plus the sidecar index.

    Called when the ACCOUNT goes. The legacy path is deleted whether or not the
    index mentions it, because an account that never opened the budgets dialog
    has a database and no index at all.
    """
    for record in load_index(username).budgets:
        delete_db_files(Config.for_user_budget(username, record.slug).db_path)
    delete_db_files(Config.for_user(username).db_path)
    Config.budgets_index_path(username).unlink(missing_ok=True)
