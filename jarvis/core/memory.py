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
        conn = sqlite3.connect(self.path)
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
