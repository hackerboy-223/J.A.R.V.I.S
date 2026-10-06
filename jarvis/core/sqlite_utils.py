from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3


DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_BUSY_TIMEOUT_MS = 10_000


def open_sqlite(
    path: Path,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    row_factory: bool = True,
) -> sqlite3.Connection:
    """Open a configured local JARVIS SQLite connection.

    Per-connection pragmas live here so every subsystem behaves consistently.
    WAL itself is enabled by prepare_sqlite() because journal_mode is persistent.
    """
    db_path = Path(path).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    timeout = max(1.0, float(timeout))
    db = sqlite3.connect(db_path, timeout=timeout)
    if row_factory:
        db.row_factory = sqlite3.Row

    busy_ms = max(DEFAULT_BUSY_TIMEOUT_MS, int(timeout * 1000))
    db.execute(f"PRAGMA busy_timeout={busy_ms}")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def prepare_sqlite(path: Path) -> str:
    """Enable persistent WAL mode and verify the database can be opened."""
    with closing(open_sqlite(path)) as db:
        row = db.execute("PRAGMA journal_mode=WAL").fetchone()
        mode = str(row[0] if row is not None else "").lower()
        if mode != "wal":
            raise RuntimeError(
                f"SQLite WAL n'a pas pu être activé (mode obtenu: {mode or 'inconnu'})."
            )
        db.execute("PRAGMA wal_autocheckpoint=1000")
        return mode
