from __future__ import annotations

from pathlib import Path
import os
import tempfile
from typing import Any

from jarvis.config import settings
from jarvis.core.changes import ChangeJournal
from jarvis.core.recent import RecentFileStore


_BLOCKED_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "jarvis.db",
    "credentials.json",
    "secrets.json",
}
_BLOCKED_PARTS = {".git", ".ssh", "__pycache__"}
_MAX_READ_BYTES = 1_500_000
_MAX_WRITE_CHARS = 1_500_000


def _workspace_root() -> Path:
    return settings.workspace_root.resolve()


def _resolve_workspace_path(raw: str) -> Path:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("path est requis.")

    root = _workspace_root()
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PermissionError("Chemin hors du workspace JARVIS interdit.") from exc

    lowered_parts = {part.lower() for part in candidate.parts}
    if candidate.name.lower() in _BLOCKED_NAMES or lowered_parts.intersection(_BLOCKED_PARTS):
        raise PermissionError("Ce fichier ou dossier sensible n'est pas accessible à l'agent.")

    return candidate


def _journal() -> ChangeJournal:
    return ChangeJournal(settings.database_path)


def _recent() -> RecentFileStore:
    return RecentFileStore(settings.database_path)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def file_read(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_workspace_path(str(args.get("path", "")))
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {path.name}")
    if path.stat().st_size > _MAX_READ_BYTES:
        raise ValueError("Fichier trop volumineux pour file_read (1,5 Mo max).")

    text = path.read_text(encoding="utf-8", errors="replace")
    relative = str(path.relative_to(_workspace_root()))
    _recent().touch(relative, "read")
    max_chars = max(200, min(int(args.get("max_chars", 30000) or 30000), 80000))
    return {
        "path": relative,
        "content": text[:max_chars],
        "truncated": len(text) > max_chars,
    }


def file_write(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_workspace_path(str(args.get("path", "")))
    content = str(args.get("content", ""))
    overwrite = bool(args.get("overwrite", False))

    if len(content) > _MAX_WRITE_CHARS:
        raise ValueError("Contenu trop volumineux (1,5 M caractères max).")
    if path.exists() and not overwrite:
        raise FileExistsError("Le fichier existe déjà. Utilise overwrite=true explicitement.")
    if path.exists() and not path.is_file():
        raise ValueError("La cible existe mais n'est pas un fichier.")

    relative = str(path.relative_to(_workspace_root()))
    before = path.read_text(encoding="utf-8", errors="strict") if path.exists() else None
    _atomic_write(path, content)
    change_id = _journal().record(relative, before, content)
    _recent().touch(relative, "write")
    return {
        "written": True,
        "path": relative,
        "chars": len(content),
        "change_id": change_id,
        "diff": ChangeJournal.diff(relative, before or "", content)[:30000],
    }


def file_patch(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_workspace_path(str(args.get("path", "")))
    old = str(args.get("old", ""))
    new = str(args.get("new", ""))
    replace_all = bool(args.get("replace_all", False))

    if not old:
        raise ValueError("old est requis pour un patch exact.")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {path.name}")
    if path.stat().st_size > _MAX_READ_BYTES:
        raise ValueError("Fichier trop volumineux pour file_patch.")

    text = path.read_text(encoding="utf-8", errors="strict")
    occurrences = text.count(old)
    if occurrences == 0:
        raise ValueError("Le bloc exact à remplacer n'a pas été trouvé.")
    if occurrences > 1 and not replace_all:
        raise ValueError(
            f"Le bloc apparaît {occurrences} fois. "
            "Affinez old ou utilisez replace_all=true explicitement."
        )

    updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    relative = str(path.relative_to(_workspace_root()))
    _atomic_write(path, updated)
    change_id = _journal().record(relative, text, updated)
    _recent().touch(relative, "patch")
    return {
        "patched": True,
        "path": relative,
        "replacements": occurrences if replace_all else 1,
        "change_id": change_id,
        "diff": ChangeJournal.diff(relative, text, updated)[:30000],
    }


def file_preview_patch(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_workspace_path(str(args.get("path", "")))
    old = str(args.get("old", ""))
    new = str(args.get("new", ""))
    replace_all = bool(args.get("replace_all", False))
    if not old:
        raise ValueError("old est requis.")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {path.name}")
    text = path.read_text(encoding="utf-8", errors="strict")
    occurrences = text.count(old)
    if occurrences == 0:
        raise ValueError("Le bloc exact à remplacer n'a pas été trouvé.")
    if occurrences > 1 and not replace_all:
        raise ValueError("Le bloc apparaît plusieurs fois ; affinez old.")
    updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    relative = str(path.relative_to(_workspace_root()))
    return {
        "path": relative,
        "replacements": occurrences if replace_all else 1,
        "diff": ChangeJournal.diff(relative, text, updated)[:50000],
    }


def file_undo(args: dict[str, Any]) -> dict[str, Any]:
    change_id = str(args.get("change_id", "")).strip()
    if not change_id:
        raise ValueError("change_id est requis.")
    return _journal().undo(change_id)


def file_changes(args: dict[str, Any] | None = None) -> dict[str, Any]:
    limit = int((args or {}).get("limit", 30) or 30)
    return {"changes": _journal().recent(limit=limit)}
