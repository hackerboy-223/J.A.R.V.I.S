from __future__ import annotations

from contextlib import closing
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class ActivityStore:
    """Persistent human-readable audit trail for runtime actions and failures."""

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
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS activity_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_activity_recent
                ON activity_events(id DESC);
                """
            )
            db.commit()

    def log(
        self,
        category: str,
        action: str,
        *,
        status: str = "ok",
        summary: str = "",
        details: dict[str, Any] | None = None,
    ) -> int:
        payload = json.dumps(details or {}, ensure_ascii=False, default=str)[:30000]
        with self._lock, closing(self._connect()) as db:
            cur = db.execute(
                """
                INSERT INTO activity_events(category, action, status, summary, details_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(category)[:80],
                    str(action)[:120],
                    str(status)[:30],
                    str(summary)[:2000],
                    payload,
                ),
            )
            db.commit()
            return int(cur.lastrowid)

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT id, category, action, status, summary, details_json, created_at
                FROM activity_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            try:
                item["details"] = json.loads(str(item.pop("details_json") or "{}"))
            except json.JSONDecodeError:
                item["details"] = {}
            items.append(item)
        return items
