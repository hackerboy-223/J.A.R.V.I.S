from __future__ import annotations

from difflib import unified_diff
from pathlib import Path
from typing import Any

from jarvis.config import settings


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


def workspace_path(raw: str) -> Path:
    """Resolve a user-facing workspace path using the same safety policy as file tools."""
    return _resolve_workspace_path(raw)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".jarvis.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def file_read(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_workspace_path(str(args.get("path", "")))
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {path.name}")
    if path.stat().st_size > _MAX_READ_BYTES:
        raise ValueError("Fichier trop volumineux pour file_read (1,5 Mo max).")

    text = path.read_text(encoding="utf-8", errors="replace")
    max_chars = max(200, min(int(args.get("max_chars", 30000) or 30000), 80000))
    return {
        "path": str(path.relative_to(_workspace_root())),
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

    _atomic_write(path, content)
    return {
        "written": True,
        "path": str(path.relative_to(_workspace_root())),
        "chars": len(content),
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
    _atomic_write(path, updated)
    return {
        "patched": True,
        "path": str(path.relative_to(_workspace_root())),
        "replacements": occurrences if replace_all else 1,
    }


def file_patch_preview(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_workspace_path(str(args.get("path", "")))
    old = str(args.get("old", ""))
    new = str(args.get("new", ""))
    replace_all = bool(args.get("replace_all", False))
    if not old:
        raise ValueError("old est requis pour un preview de patch.")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {path.name}")
    text = path.read_text(encoding="utf-8", errors="strict")
    occurrences = text.count(old)
    if occurrences == 0:
        raise ValueError("Le bloc exact à remplacer n'a pas été trouvé.")
    if occurrences > 1 and not replace_all:
        raise ValueError(
            f"Le bloc apparaît {occurrences} fois. Affinez old ou utilisez replace_all=true."
        )
    updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    diff = "".join(
        unified_diff(
            text.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
    )
    return {
        "path": str(path.relative_to(_workspace_root())),
        "occurrences": occurrences,
        "diff": diff[:120_000],
        "truncated": len(diff) > 120_000,
    }
