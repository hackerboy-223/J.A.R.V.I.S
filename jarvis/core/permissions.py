from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import sqlite3
import threading
from typing import Callable
from jarvis.core.sqlite_utils import open_sqlite, prepare_sqlite


class PermissionDecision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class PermissionResult:
    capability: str
    decision: PermissionDecision
    source: str


class PermissionEngine:
    """Persistent permission policy with explicit allow/ask/deny semantics."""

    DEFAULTS: dict[str, PermissionDecision] = {
        "system.read": PermissionDecision.ALLOW,
        "memory.read": PermissionDecision.ALLOW,
        "knowledge.read": PermissionDecision.ALLOW,
        "clipboard.write": PermissionDecision.ALLOW,
        "clipboard.read": PermissionDecision.ASK,
        "screen.read": PermissionDecision.ASK,
        "windows.inspect": PermissionDecision.ALLOW,
        "windows.focus": PermissionDecision.ASK,
        "ui.click": PermissionDecision.ASK,
        "ui.type": PermissionDecision.ASK,
        "files.read": PermissionDecision.ALLOW,
        "files.write": PermissionDecision.ASK,
        "files.move": PermissionDecision.ASK,
        "network.web": PermissionDecision.ALLOW,
        "mcp.call": PermissionDecision.ASK,
        "scheduler.write": PermissionDecision.ASK,
        "sandbox.run": PermissionDecision.ASK,
    }

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        self._session: dict[str, PermissionDecision] = {}
        prepare_sqlite(self.db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return open_sqlite(self.db_path)

    def _init_db(self) -> None:
        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS permissions (
                    capability TEXT PRIMARY KEY,
                    decision TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            db.commit()

    def list(self) -> list[dict[str, str]]:
        persisted: dict[str, str] = {}
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                "SELECT capability, decision FROM permissions ORDER BY capability"
            ).fetchall()
        for row in rows:
            persisted[str(row["capability"])] = str(row["decision"])

        capabilities = sorted(set(self.DEFAULTS) | set(persisted) | set(self._session))
        return [
            {
                "capability": name,
                "decision": self.get(name).decision.value,
                "source": self.get(name).source,
            }
            for name in capabilities
        ]

    def get(self, capability: str) -> PermissionResult:
        name = capability.strip().lower()
        if not name:
            raise ValueError("capability est requis.")
        with self._lock:
            if name in self._session:
                return PermissionResult(name, self._session[name], "session")
            with closing(self._connect()) as db:
                row = db.execute(
                    "SELECT decision FROM permissions WHERE capability = ?",
                    (name,),
                ).fetchone()
        if row is not None:
            return PermissionResult(name, PermissionDecision(str(row["decision"])), "persistent")
        return PermissionResult(
            name,
            self.DEFAULTS.get(name, PermissionDecision.ASK),
            "default",
        )

    def set(self, capability: str, decision: str, *, scope: str = "always") -> PermissionResult:
        name = capability.strip().lower()
        value = PermissionDecision(decision.strip().lower())
        if scope == "session":
            with self._lock:
                self._session[name] = value
            return PermissionResult(name, value, "session")
        if scope != "always":
            raise ValueError("scope doit être session ou always.")
        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                INSERT INTO permissions(capability, decision) VALUES(?, ?)
                ON CONFLICT(capability) DO UPDATE SET
                    decision=excluded.decision,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (name, value.value),
            )
            db.commit()
        return PermissionResult(name, value, "persistent")

    def clear_session(self) -> None:
        with self._lock:
            self._session.clear()

    def authorize(
        self,
        capability: str,
        prompt: str,
        confirm: Callable[[str], bool] | None = None,
    ) -> bool:
        result = self.get(capability)
        if result.decision is PermissionDecision.ALLOW:
            return True
        if result.decision is PermissionDecision.DENY:
            return False
        return bool(confirm and confirm(prompt))
