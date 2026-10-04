from __future__ import annotations

from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
from typing import Any

from jarvis.config import settings
from jarvis.core.platform_store import PlatformStore


class HealthService:
    def __init__(self, store: PlatformStore) -> None:
        self.store = store

    def snapshot(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def add(name: str, ok: bool, detail: str) -> None:
            checks.append({"name": name, "ok": bool(ok), "detail": detail})

        try:
            with closing(sqlite3.connect(settings.database_path, timeout=3)) as db:
                db.execute("SELECT 1").fetchone()
            add("sqlite", True, str(settings.database_path))
        except Exception as exc:
            add("sqlite", False, str(exc))

        workspace = Path(settings.workspace_root)
        add(
            "workspace",
            workspace.exists() and workspace.is_dir(),
            str(workspace),
        )

        usage = shutil.disk_usage(settings.database_path.parent)
        free_gb = usage.free / (1024 ** 3)
        add("disk", free_gb > 1.0, f"{free_gb:.1f} GB libres")

        add(
            "scheduler",
            bool(settings.scheduler_enabled),
            "activé" if settings.scheduler_enabled else "désactivé",
        )
        add(
            "pc_control",
            bool(settings.allow_pc_control),
            "autorisé" if settings.allow_pc_control else "verrouillé",
        )
        add(
            "llm",
            True,
            f"{settings.llm_provider} · {settings.llm_model}",
        )

        healthy = all(item["ok"] for item in checks if item["name"] != "pc_control")
        return {"healthy": healthy, "checks": checks}
