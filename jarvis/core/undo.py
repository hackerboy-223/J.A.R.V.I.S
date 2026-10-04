from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
import hashlib
import threading
import uuid


@dataclass
class FileSnapshot:
    id: str
    path: Path
    before: str
    after: str
    before_hash: str
    after_hash: str


class UndoManager:
    """In-memory reversible text-file edits with exact hash checks."""

    def __init__(self, limit: int = 40) -> None:
        self.limit = max(1, int(limit))
        self._lock = threading.RLock()
        self._items: list[FileSnapshot] = []

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def record(self, path: Path, before: str, after: str) -> str:
        snap = FileSnapshot(
            id=uuid.uuid4().hex[:12],
            path=path.resolve(),
            before=before,
            after=after,
            before_hash=self._hash(before),
            after_hash=self._hash(after),
        )
        with self._lock:
            self._items.append(snap)
            self._items = self._items[-self.limit :]
        return snap.id

    def diff(self, before: str, after: str, name: str = "file") -> str:
        return "".join(
            unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{name}",
                tofile=f"b/{name}",
            )
        )

    def undo(self, snapshot_id: str) -> dict[str, str]:
        with self._lock:
            snap = next((item for item in reversed(self._items) if item.id == snapshot_id), None)
        if snap is None:
            raise ValueError("Snapshot introuvable.")
        current = snap.path.read_text(encoding="utf-8", errors="strict")
        if self._hash(current) != snap.after_hash:
            raise RuntimeError("Le fichier a changé depuis le patch ; undo refusé.")
        tmp = snap.path.with_suffix(snap.path.suffix + ".jarvis.tmp")
        tmp.write_text(snap.before, encoding="utf-8")
        tmp.replace(snap.path)
        return {"undone": snapshot_id, "path": str(snap.path)}
