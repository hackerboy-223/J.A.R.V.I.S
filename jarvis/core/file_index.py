from __future__ import annotations

from contextlib import closing
from pathlib import Path
import os
import sqlite3
import threading
from typing import Any


class FileIndex:
    """Fast local filename/path index using SQLite FTS5."""

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
                CREATE VIRTUAL TABLE IF NOT EXISTS file_index USING fts5(
                    path UNINDEXED,
                    name,
                    extension,
                    workspace_id UNINDEXED,
                    modified UNINDEXED,
                    size UNINDEXED
                );
                """
            )
            db.commit()

    def rebuild(
        self,
        root: Path,
        *,
        workspace_id: str = "default",
        max_files: int = 100_000,
    ) -> dict[str, Any]:
        root = root.expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError("Workspace introuvable.")

        blocked = {".git", "node_modules", ".next", "__pycache__", ".venv", "venv"}
        rows: list[tuple[str, str, str, str, float, int]] = []
        for current, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d.lower() not in blocked]
            for name in files:
                path = Path(current) / name
                try:
                    stat = path.stat()
                except OSError:
                    continue
                rows.append(
                    (
                        str(path),
                        name,
                        path.suffix.lower(),
                        workspace_id,
                        stat.st_mtime,
                        stat.st_size,
                    )
                )
                if len(rows) >= max_files:
                    break
            if len(rows) >= max_files:
                break

        with self._lock, closing(self._connect()) as db:
            db.execute("DELETE FROM file_index WHERE workspace_id = ?", (workspace_id,))
            db.executemany(
                """
                INSERT INTO file_index(path, name, extension, workspace_id, modified, size)
                VALUES(?,?,?,?,?,?)
                """,
                rows,
            )
            db.commit()

        return {"indexed": len(rows), "root": str(root), "workspace_id": workspace_id}

    def search(self, query: str, limit: int = 40) -> list[dict[str, Any]]:
        clean = " ".join(query.strip().split())
        if not clean:
            return []
        fts = " ".join(f'"{token.replace(chr(34), "")}"*' for token in clean.split())
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT path, name, extension, workspace_id, modified, size,
                       bm25(file_index) AS rank
                FROM file_index
                WHERE file_index MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts, max(1, min(int(limit), 200))),
            ).fetchall()
        return [dict(row) for row in rows]
