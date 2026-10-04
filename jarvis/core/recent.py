from __future__ import annotations

from contextlib import closing
import sqlite3
import threading
from pathlib import Path
from typing import Any


class RecentFileStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _init_db(self) -> None:
        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS recent_files (
                    path TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    last_used_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.commit()

    def touch(self, path: str, action: str = "read") -> None:
        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                INSERT INTO recent_files(path, action)
                VALUES (?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    action=excluded.action,
                    last_used_at=CURRENT_TIMESTAMP
                """,
                (path[:2000], action[:40]),
            )
            db.commit()

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT path, action, last_used_at
                FROM recent_files
                ORDER BY last_used_at DESC
                LIMIT ?
                """,
                (max(1, min(int(limit), 200)),),
            ).fetchall()
        return [dict(row) for row in rows]
