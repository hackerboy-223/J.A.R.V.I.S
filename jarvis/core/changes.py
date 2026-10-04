from __future__ import annotations

from contextlib import closing
import difflib
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from jarvis.config import settings


class ChangeJournal:
    """File diff/snapshot journal enabling preview and best-effort undo."""

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
                CREATE TABLE IF NOT EXISTS file_changes (
                    id TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    before_text TEXT,
                    after_text TEXT,
                    undone INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_file_changes_recent
                ON file_changes(created_at DESC);
                """
            )
            db.commit()

    @staticmethod
    def diff(path: str, before: str, after: str) -> str:
        return "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )

    def record(self, path: str, before: str | None, after: str | None) -> str:
        change_id = uuid.uuid4().hex[:16]
        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                INSERT INTO file_changes(id, path, before_text, after_text)
                VALUES (?, ?, ?, ?)
                """,
                (change_id, path, before, after),
            )
            db.commit()
        return change_id

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT id, path, undone, created_at
                FROM file_changes
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(int(limit), 200)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, change_id: str) -> dict[str, Any] | None:
        with self._lock, closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM file_changes WHERE id=?",
                (change_id,),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["diff"] = self.diff(
            str(item["path"]),
            str(item.get("before_text") or ""),
            str(item.get("after_text") or ""),
        )
        return item

    def diff_for(self, change_id: str) -> str:
        item = self.get(change_id)
        if item is None:
            raise ValueError("Modification introuvable.")
        return str(item.get("diff") or "")

    def undo(self, change_id: str) -> dict[str, Any]:
        with self._lock, closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM file_changes WHERE id=?", (change_id,)
            ).fetchone()
        if row is None:
            raise ValueError("Modification introuvable.")
        if int(row["undone"]):
            raise ValueError("Cette modification a déjà été annulée.")

        root = settings.workspace_root.resolve()
        path = (root / str(row["path"])).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise PermissionError("Chemin hors workspace.") from exc

        before = row["before_text"]
        current = path.read_text(encoding="utf-8", errors="strict") if path.exists() else None
        expected_after = row["after_text"]
        if current != expected_after:
            raise RuntimeError(
                "Le fichier a changé depuis l'opération. Undo automatique refusé pour éviter d'écraser des modifications récentes."
            )

        if before is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(before), encoding="utf-8")

        with self._lock, closing(self._connect()) as db:
            db.execute("UPDATE file_changes SET undone=1 WHERE id=?", (change_id,))
            db.commit()
        return {"undone": True, "change_id": change_id, "path": str(row["path"])}
