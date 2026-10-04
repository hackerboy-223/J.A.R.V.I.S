from __future__ import annotations

from contextlib import closing
import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any


class MissionStore:
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
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    workspace_id TEXT,
                    operator_id TEXT NOT NULL UNIQUE,
                    mode TEXT NOT NULL DEFAULT 'operative',
                    status TEXT NOT NULL DEFAULT 'active',
                    state_json TEXT NOT NULL DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_missions_recent
                ON missions(updated_at DESC);
                """
            )
            db.commit()

    def create(
        self,
        title: str,
        *,
        workspace_id: str | None = None,
        mode: str = "operative",
    ) -> dict[str, Any]:
        mission_id = uuid.uuid4().hex[:12]
        operator_id = f"mission:{mission_id}"
        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                INSERT INTO missions(id, title, workspace_id, operator_id, mode)
                VALUES (?, ?, ?, ?, ?)
                """,
                (mission_id, title.strip()[:180] or "Nouvelle mission", workspace_id, operator_id, mode),
            )
            db.commit()
        return self.get(mission_id) or {}

    def update_state(self, mission_id: str, state: dict[str, Any], status: str | None = None) -> None:
        payload = json.dumps(state, ensure_ascii=False, default=str)[:50000]
        with self._lock, closing(self._connect()) as db:
            if status is None:
                db.execute(
                    """
                    UPDATE missions
                    SET state_json=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (payload, mission_id),
                )
            else:
                db.execute(
                    """
                    UPDATE missions
                    SET state_json=?, status=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (payload, status[:30], mission_id),
                )
            db.commit()

    def set_status(self, mission_id: str, status: str) -> None:
        with self._lock, closing(self._connect()) as db:
            db.execute(
                "UPDATE missions SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status[:30], mission_id),
            )
            db.commit()

    def get(self, mission_id: str) -> dict[str, Any] | None:
        with self._lock, closing(self._connect()) as db:
            row = db.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
        return self._decode(dict(row)) if row else None

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM missions ORDER BY updated_at DESC LIMIT ?",
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        return [self._decode(dict(row)) for row in rows]

    @staticmethod
    def _decode(item: dict[str, Any]) -> dict[str, Any]:
        try:
            item["state"] = json.loads(str(item.pop("state_json") or "{}"))
        except json.JSONDecodeError:
            item["state"] = {}
        return item
