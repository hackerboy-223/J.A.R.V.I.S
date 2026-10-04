from __future__ import annotations

from contextlib import closing
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any


class WorkspaceStore:
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
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    root_path TEXT NOT NULL UNIQUE,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_opened_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            db.commit()

    def add(self, name: str, root_path: str | Path, favorite: bool = False) -> dict[str, Any]:
        root = Path(root_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError("Le workspace doit pointer vers un dossier existant.")
        workspace_id = uuid.uuid4().hex[:12]
        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                INSERT INTO workspaces(id, name, root_path, favorite)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(root_path) DO UPDATE SET
                    name=excluded.name,
                    favorite=excluded.favorite,
                    last_opened_at=CURRENT_TIMESTAMP
                """,
                (workspace_id, name.strip()[:120] or root.name, str(root), int(favorite)),
            )
            db.commit()
            row = db.execute(
                "SELECT * FROM workspaces WHERE root_path=?", (str(root),)
            ).fetchone()
        return dict(row) if row else {}

    def touch(self, workspace_id: str) -> None:
        with self._lock, closing(self._connect()) as db:
            db.execute(
                "UPDATE workspaces SET last_opened_at=CURRENT_TIMESTAMP WHERE id=?",
                (workspace_id,),
            )
            db.commit()

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT * FROM workspaces
                ORDER BY favorite DESC, last_opened_at DESC
                LIMIT ?
                """,
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, workspace_id: str) -> dict[str, Any] | None:
        with self._lock, closing(self._connect()) as db:
            row = db.execute("SELECT * FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
        return dict(row) if row else None
