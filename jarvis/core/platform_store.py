from __future__ import annotations

from contextlib import closing
from pathlib import Path
import json
import sqlite3
import threading
import uuid
from typing import Any


class PlatformStore:
    """Persistence for activity, workspaces, missions and resumable checkpoints."""

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
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    root_path TEXT NOT NULL UNIQUE,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    workspace_id TEXT,
                    mode TEXT NOT NULL DEFAULT 'standard',
                    status TEXT NOT NULL DEFAULT 'active',
                    state_json TEXT NOT NULL DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS mission_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_activity_created
                ON activity_events(id DESC);
                CREATE INDEX IF NOT EXISTS idx_mission_checkpoints
                ON mission_checkpoints(mission_id, id DESC);
                """
            )
            db.commit()

    def log(self, category: str, action: str, detail: dict[str, Any] | None = None) -> None:
        with self._lock, closing(self._connect()) as db:
            db.execute(
                "INSERT INTO activity_events(category, action, detail_json) VALUES(?,?,?)",
                (
                    category.strip()[:80] or "system",
                    action.strip()[:160] or "event",
                    json.dumps(detail or {}, ensure_ascii=False, default=str)[:20000],
                ),
            )
            db.commit()

    def activity(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM activity_events ORDER BY id DESC LIMIT ?",
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["detail"] = json.loads(item.pop("detail_json"))
            except Exception:
                item["detail"] = {}
            result.append(item)
        return result

    def add_workspace(self, name: str, root_path: str, favorite: bool = False) -> dict[str, Any]:
        workspace_id = uuid.uuid4().hex[:12]
        root = str(Path(root_path).expanduser().resolve())
        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                INSERT INTO workspaces(id, name, root_path, favorite)
                VALUES(?,?,?,?)
                ON CONFLICT(root_path) DO UPDATE SET
                    name=excluded.name,
                    favorite=excluded.favorite,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (workspace_id, name.strip()[:160] or Path(root).name, root, int(favorite)),
            )
            db.commit()
            row = db.execute("SELECT * FROM workspaces WHERE root_path = ?", (root,)).fetchone()
        return dict(row)

    def workspaces(self) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM workspaces ORDER BY favorite DESC, updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def create_mission(
        self,
        title: str,
        workspace_id: str | None = None,
        mode: str = "standard",
    ) -> dict[str, Any]:
        mission_id = uuid.uuid4().hex[:12]
        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                INSERT INTO missions(id, title, workspace_id, mode)
                VALUES(?,?,?,?)
                """,
                (mission_id, title.strip()[:220] or "Nouvelle mission", workspace_id, mode),
            )
            db.commit()
            row = db.execute("SELECT * FROM missions WHERE id = ?", (mission_id,)).fetchone()
        return dict(row)

    def missions(self, status: str | None = None) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as db:
            if status:
                rows = db.execute(
                    "SELECT * FROM missions WHERE status = ? ORDER BY updated_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = db.execute("SELECT * FROM missions ORDER BY updated_at DESC").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["state"] = json.loads(item.pop("state_json"))
            except Exception:
                item["state"] = {}
            result.append(item)
        return result

    def checkpoint(self, mission_id: str, state: dict[str, Any]) -> None:
        payload = json.dumps(state, ensure_ascii=False, default=str)[:50000]
        with self._lock, closing(self._connect()) as db:
            db.execute(
                "UPDATE missions SET state_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (payload, mission_id),
            )
            db.execute(
                "INSERT INTO mission_checkpoints(mission_id, state_json) VALUES(?,?)",
                (mission_id, payload),
            )
            db.commit()

    def latest_checkpoint(self, mission_id: str) -> dict[str, Any]:
        with self._lock, closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT state_json, created_at FROM mission_checkpoints
                WHERE mission_id=? ORDER BY id DESC LIMIT 1
                """,
                (mission_id,),
            ).fetchone()
        if row is None:
            return {}
        try:
            state = json.loads(str(row["state_json"]))
        except Exception:
            state = {}
        return {"state": state, "created_at": row["created_at"]}
