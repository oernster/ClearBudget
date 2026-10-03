"""Builders shared by the full-backup tests: real databases in a scratch dir."""

from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path

from clear_budget.auth.full_backup import USERS_DB_NAME
from clear_budget.auth.user_store import UserStore
from clear_budget.infrastructure.sqlite.database import Database

MARKER_KEY = "marker"


def real_users_db(path: Path, *usernames: str) -> None:
    """An accounts database holding ``usernames`` (default: oliver)."""
    store = UserStore(path)
    for username in usernames or ("oliver",):
        store.create_user(username, "a-password-12345", is_admin=True)
    store.close()


def real_budget_db(path: Path, marker: str | None = None) -> None:
    """A budget database with the full schema, optionally holding a marker."""
    db = Database(path)
    db.connect()
    db.create_schema()
    db.close()
    if marker is not None:
        set_marker(path, marker)


def set_marker(path: Path, marker: str) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (MARKER_KEY, marker),
        )
        conn.commit()
    finally:
        conn.close()


def marker_of(path: Path) -> str | None:
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (MARKER_KEY,)
        ).fetchone()
    finally:
        conn.close()
    return None if row is None else row[0]


def data_dir(tmp_path: Path) -> Path:
    """A data directory as the app leaves it, plus files a backup ignores."""
    app_dir = tmp_path / "data"
    app_dir.mkdir(parents=True)
    real_users_db(app_dir / USERS_DB_NAME)
    real_budget_db(app_dir / "budget_oliver.db")
    real_budget_db(app_dir / "budget_oliver__household.db")
    (app_dir / "budgets_oliver.json").write_text("{}", encoding="utf-8")
    (app_dir / "ui_settings.json").write_text("{}", encoding="utf-8")
    (app_dir / "arrows").mkdir()
    (app_dir / "arrows" / "up.png").write_bytes(b"\x89PNG")
    return app_dir


def rewrite_zip(
    source: Path,
    dest: Path,
    *,
    replace: dict[str, bytes] | None = None,
    extra: tuple[tuple[str, bytes], ...] = (),
    compression: int = zipfile.ZIP_DEFLATED,
) -> None:
    """Copy ``source`` to ``dest``, swapping or adding members on the way."""
    replace = replace or {}
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(dest, "w", compression) as out:
        for name in src.namelist():
            out.writestr(name, replace.get(name, src.read(name)))
        for name, data in extra:
            out.writestr(name, data)


def wreck_table_page(path: Path, table: str) -> bytes:
    """``path``'s bytes with ``table``'s root page overwritten, schema intact."""
    conn = sqlite3.connect(str(path))
    try:
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        root = conn.execute(
            "SELECT rootpage FROM sqlite_master WHERE name = ?", (table,)
        ).fetchone()[0]
    finally:
        conn.close()
    raw = bytearray(path.read_bytes())
    start = (root - 1) * page_size
    raw[start : start + page_size] = b"\xab" * page_size
    return bytes(raw)
