from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterable


_SKIP_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", "node_modules", ".next",
    ".venv", "venv", "dist", "build", ".cache",
}


class FileIndex:
    """Fast filename/path index backed by SQLite FTS5."""

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
                CREATE VIRTUAL TABLE IF NOT EXISTS file_search USING fts5(
                    workspace_id UNINDEXED,
                    path,
                    name,
                    extension,
                    modified UNINDEXED,
                    size UNINDEXED,
                    tokenize='unicode61'
                )
                """
            )
            db.commit()

    def _walk(self, root: Path, max_files: int) -> Iterable[Path]:
        pending = [root]
        seen = 0
        while pending and seen < max_files:
            current = pending.pop()
            try:
                entries = list(os.scandir(current))
            except (OSError, PermissionError):
                continue
            for entry in entries:
                if entry.name in _SKIP_DIRS:
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        seen += 1
                        yield Path(entry.path)
                        if seen >= max_files:
                            return
                except OSError:
                    continue

    def index_workspace(
        self,
        workspace_id: str,
        root_path: str | Path,
        *,
        max_files: int = 50000,
    ) -> dict[str, Any]:
        root = Path(root_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError("Workspace introuvable.")

        rows: list[tuple[Any, ...]] = []
        for path in self._walk(root, max(100, min(int(max_files), 200000))):
            try:
                stat = path.stat()
                relative = str(path.relative_to(root))
            except (OSError, ValueError):
                continue
            rows.append(
                (
                    workspace_id,
                    relative,
                    path.name,
                    path.suffix.lower(),
                    float(stat.st_mtime),
                    int(stat.st_size),
                )
            )

        with self._lock, closing(self._connect()) as db:
            db.execute("DELETE FROM file_search WHERE workspace_id=?", (workspace_id,))
            db.executemany(
                """
                INSERT INTO file_search(workspace_id, path, name, extension, modified, size)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            db.commit()
        return {"workspace_id": workspace_id, "indexed": len(rows), "root": str(root)}

    @staticmethod
    def _query(text: str) -> str:
        tokens = [token.replace('"', "") for token in text.split() if token.strip()]
        return " AND ".join(f'"{token}"*' for token in tokens[:12])

    def search(
        self,
        query: str,
        *,
        workspace_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        match = self._query(query)
        if not match:
            return []
        params: list[Any] = [match]
        where = "file_search MATCH ?"
        if workspace_id:
            where += " AND workspace_id=?"
            params.append(workspace_id)
        params.append(max(1, min(int(limit), 200)))
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                f"""
                SELECT workspace_id, path, name, extension, modified, size,
                       bm25(file_search) AS rank
                FROM file_search
                WHERE {where}
                ORDER BY rank
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]
