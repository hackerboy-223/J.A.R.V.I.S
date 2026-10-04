from __future__ import annotations

from contextlib import closing
import sqlite3
import threading
from pathlib import Path
from typing import Callable, Literal


Decision = Literal["allow", "ask", "deny"]
Scope = Literal["once", "session", "always"]
ConfirmFn = Callable[[str], bool]


_DEFAULTS: dict[str, Decision] = {
    "system.read": "allow",
    "knowledge.read": "allow",
    "mcp.inspect": "allow",
    "network.web": "allow",
    "workspace.read": "allow",
    "files.search": "allow",
    "files.history": "allow",
    "files.index": "ask",
    "windows.inspect": "ask",
    "windows.focus": "ask",
    "clipboard.write": "allow",
    "clipboard.read": "ask",
    "screen.capture": "ask",
    "files.write": "ask",
    "files.undo": "ask",
    "ui.inspect": "ask",
    "ui.automation": "ask",
    "pc.control": "ask",
    "python.sandbox": "ask",
    "mcp.call": "ask",
    "scheduler.mutate": "ask",
    "mission.manage": "ask",
    "workspace.manage": "ask",
    "scheduler.read": "allow",
    "update.download": "ask",
    "update.install": "ask",
}


class PermissionEngine:
    """Single permission policy shared by tools, UI and API."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        self._session: dict[str, Decision] = {}
        self._once: dict[str, Decision] = {}
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _init_db(self) -> None:
        with self._lock, closing(self._connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS permission_rules (
                    capability TEXT PRIMARY KEY,
                    decision TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS permission_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capability TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    source TEXT NOT NULL,
                    reason TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            db.commit()

    def _default(self, capability: str) -> Decision:
        if capability in _DEFAULTS:
            return _DEFAULTS[capability]
        parts = capability.split(".")
        while len(parts) > 1:
            parts.pop()
            prefix = ".".join(parts)
            if prefix in _DEFAULTS:
                return _DEFAULTS[prefix]
        return "ask"

    def get(self, capability: str) -> Decision:
        clean = capability.strip().lower()
        with self._lock:
            if clean in self._once:
                return self._once[clean]
            if clean in self._session:
                return self._session[clean]
        with self._lock, closing(self._connect()) as db:
            row = db.execute(
                "SELECT decision FROM permission_rules WHERE capability = ?",
                (clean,),
            ).fetchone()
        if row is not None and row["decision"] in {"allow", "ask", "deny"}:
            return str(row["decision"])  # type: ignore[return-value]
        return self._default(clean)

    def set(self, capability: str, decision: Decision, scope: Scope = "always") -> None:
        clean = capability.strip().lower()
        if decision not in {"allow", "ask", "deny"}:
            raise ValueError("decision doit être allow, ask ou deny.")
        if scope not in {"once", "session", "always"}:
            raise ValueError("scope doit être once, session ou always.")

        with self._lock:
            if scope == "once":
                self._once[clean] = decision
                return
            if scope == "session":
                self._session[clean] = decision
                return

        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                INSERT INTO permission_rules(capability, decision)
                VALUES (?, ?)
                ON CONFLICT(capability) DO UPDATE SET
                    decision=excluded.decision,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (clean, decision),
            )
            db.commit()

    def reset(self, capability: str) -> None:
        clean = capability.strip().lower()
        with self._lock:
            self._once.pop(clean, None)
            self._session.pop(clean, None)
        with self._lock, closing(self._connect()) as db:
            db.execute("DELETE FROM permission_rules WHERE capability = ?", (clean,))
            db.commit()

    def _audit(self, capability: str, decision: Decision, source: str, reason: str) -> None:
        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                INSERT INTO permission_audit(capability, decision, source, reason)
                VALUES (?, ?, ?, ?)
                """,
                (capability, decision, source[:40], reason[:2000]),
            )
            db.commit()

    def authorize(
        self,
        capability: str,
        reason: str,
        confirm: ConfirmFn | None = None,
    ) -> bool:
        clean = capability.strip().lower()
        decision = self.get(clean)

        with self._lock:
            if clean in self._once:
                self._once.pop(clean, None)

        if decision == "allow":
            self._audit(clean, "allow", "rule", reason)
            return True
        if decision == "deny":
            self._audit(clean, "deny", "rule", reason)
            return False

        accepted = bool(confirm(reason)) if confirm is not None else False
        self._audit(clean, "allow" if accepted else "deny", "prompt", reason)
        return accepted

    def list_rules(self) -> list[dict[str, str]]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                "SELECT capability, decision, updated_at FROM permission_rules ORDER BY capability"
            ).fetchall()
        persistent = [dict(row) for row in rows]
        with self._lock:
            session = [
                {"capability": key, "decision": value, "updated_at": "session"}
                for key, value in sorted(self._session.items())
            ]
            once = [
                {"capability": key, "decision": value, "updated_at": "once"}
                for key, value in sorted(self._once.items())
            ]
        return persistent + session + once

    def effective(self) -> list[dict[str, str]]:
        keys = set(_DEFAULTS)
        keys.update(item["capability"] for item in self.list_rules())
        return [
            {"capability": key, "decision": self.get(key)}
            for key in sorted(keys)
        ]
