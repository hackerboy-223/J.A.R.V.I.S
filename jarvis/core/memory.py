from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class MemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS facts (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS action_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS agent_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL,
                    workflow TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS operative_state (
                    operator_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS operative_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operator_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_operative_runs_operator
                ON operative_runs(operator_id, id DESC);
                """
            )

    def add_message(self, role: str, content: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO messages(role, content) VALUES (?, ?)", (role, content))
            db.commit()

    def recent_messages(self, limit: int = 24) -> list[dict[str, str]]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def set_fact(self, key: str, value: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO facts(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
                """,
                (key, value),
            )
            db.commit()

    def facts(self) -> dict[str, str]:
        with self._lock, self._connect() as db:
            rows = db.execute("SELECT key, value FROM facts ORDER BY key").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def log_action(self, tool: str, args: dict[str, Any], result: Any) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO action_log(tool,args_json,result_json) VALUES(?,?,?)",
                (tool, json.dumps(args), json.dumps(result, default=str)),
            )
            db.commit()


    def add_agent_result(self, task: str, workflow: str, summary: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO agent_results(task, workflow, summary) VALUES(?,?,?)",
                (task[:4000], workflow[:40], summary[:12000]),
            )
            db.execute(
                """
                DELETE FROM agent_results
                WHERE id NOT IN (
                    SELECT id FROM agent_results ORDER BY id DESC LIMIT 50
                )
                """
            )
            db.commit()

    def recent_agent_results(self, limit: int = 8) -> list[dict[str, str]]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                SELECT task, workflow, summary, created_at
                FROM agent_results
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]


    def get_operative_state(self, operator_id: str) -> dict[str, Any]:
        clean = operator_id.strip()[:120] or "main"
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT state_json FROM operative_state WHERE operator_id = ?",
                (clean,),
            ).fetchone()
        if row is None:
            return {}
        try:
            value = json.loads(str(row["state_json"]))
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    def set_operative_state(self, operator_id: str, state: dict[str, Any]) -> None:
        clean = operator_id.strip()[:120] or "main"
        payload = json.dumps(state, ensure_ascii=False, default=str)[:30000]
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO operative_state(operator_id, state_json)
                VALUES (?, ?)
                ON CONFLICT(operator_id) DO UPDATE SET
                    state_json=excluded.state_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (clean, payload),
            )
            db.commit()

    def add_operative_run(self, operator_id: str, prompt: str, answer: str) -> None:
        clean = operator_id.strip()[:120] or "main"
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO operative_runs(operator_id, prompt, answer)
                VALUES (?, ?, ?)
                """,
                (clean, prompt[:6000], answer[:16000]),
            )
            db.execute(
                """
                DELETE FROM operative_runs
                WHERE id NOT IN (
                    SELECT id FROM operative_runs
                    WHERE operator_id = ?
                    ORDER BY id DESC
                    LIMIT 30
                )
                AND operator_id = ?
                """,
                (clean, clean),
            )
            db.commit()

    def recent_operative_runs(
        self,
        operator_id: str,
        limit: int = 6,
    ) -> list[dict[str, str]]:
        clean = operator_id.strip()[:120] or "main"
        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                SELECT prompt, answer, created_at
                FROM operative_runs
                WHERE operator_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (clean, max(1, min(int(limit), 20))),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]
