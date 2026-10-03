from __future__ import annotations

from datetime import datetime
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from croniter import croniter


TaskCallback = Callable[[dict[str, Any]], None]


class TaskScheduler:
    """Small persistent SQLite scheduler for once/interval/cron agent tasks."""

    def __init__(
        self,
        db_path: Path,
        callback: TaskCallback,
        poll_seconds: float = 1.0,
    ) -> None:
        self.db_path = db_path
        self.callback = callback
        self.poll_seconds = max(0.5, float(poll_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _init_db(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    schedule_type TEXT NOT NULL,
                    schedule_value TEXT NOT NULL,
                    agent_mode TEXT NOT NULL DEFAULT 'operative',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    next_run_at REAL,
                    last_run_at REAL,
                    last_error TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_scheduled_due
                ON scheduled_tasks(enabled, next_run_at);
                """
            )

    @staticmethod
    def _next_run(schedule_type: str, schedule_value: str, now: float | None = None) -> float:
        now = time.time() if now is None else float(now)
        kind = schedule_type.strip().lower()
        value = schedule_value.strip()

        if kind == "interval":
            seconds = float(value)
            if seconds < 60:
                raise ValueError("L'intervalle minimum est de 60 secondes.")
            return now + seconds

        if kind == "once":
            normalized = value.replace("Z", "+00:00")
            when = datetime.fromisoformat(normalized)
            if when.tzinfo is None:
                when = when.astimezone()
            ts = when.timestamp()
            if ts <= now:
                raise ValueError("La date de la tâche doit être dans le futur.")
            return ts

        if kind == "cron":
            return float(croniter(value, datetime.now().astimezone()).get_next(datetime).timestamp())

        raise ValueError("schedule_type doit être once, interval ou cron.")

    def create(
        self,
        prompt: str,
        schedule_type: str,
        schedule_value: str,
        agent_mode: str = "operative",
    ) -> dict[str, Any]:
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("prompt est requis.")

        task_id = uuid.uuid4().hex[:12]
        next_run = self._next_run(schedule_type, schedule_value)
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO scheduled_tasks(
                    id, prompt, schedule_type, schedule_value,
                    agent_mode, enabled, next_run_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    task_id,
                    clean_prompt[:8000],
                    schedule_type.strip().lower(),
                    schedule_value.strip(),
                    agent_mode.strip().lower() or "operative",
                    next_run,
                ),
            )
            db.commit()
        return self.get(task_id)

    def get(self, task_id: str) -> dict[str, Any]:
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT * FROM scheduled_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Tâche introuvable : {task_id}")
        return dict(row)

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                SELECT * FROM scheduled_tasks
                ORDER BY enabled DESC, next_run_at ASC, created_at DESC
                LIMIT ?
                """,
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def pause(self, task_id: str) -> dict[str, Any]:
        with self._lock, self._connect() as db:
            cur = db.execute(
                "UPDATE scheduled_tasks SET enabled = 0 WHERE id = ?",
                (task_id,),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Tâche introuvable : {task_id}")
            db.commit()
        return self.get(task_id)

    def resume(self, task_id: str) -> dict[str, Any]:
        task = self.get(task_id)
        next_run = self._next_run(task["schedule_type"], task["schedule_value"])
        with self._lock, self._connect() as db:
            db.execute(
                """
                UPDATE scheduled_tasks
                SET enabled = 1, next_run_at = ?, last_error = NULL
                WHERE id = ?
                """,
                (next_run, task_id),
            )
            db.commit()
        return self.get(task_id)

    def cancel(self, task_id: str) -> dict[str, Any]:
        task = self.get(task_id)
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
            db.commit()
        return {"cancelled": True, "id": task_id, "prompt": task["prompt"]}

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="jarvis-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _claim_due(self) -> list[dict[str, Any]]:
        now = time.time()
        claimed: list[dict[str, Any]] = []
        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                SELECT * FROM scheduled_tasks
                WHERE enabled = 1
                  AND next_run_at IS NOT NULL
                  AND next_run_at <= ?
                ORDER BY next_run_at ASC
                LIMIT 4
                """,
                (now,),
            ).fetchall()

            for row in rows:
                task = dict(row)
                if task["schedule_type"] == "once":
                    enabled = 0
                    next_run = None
                else:
                    enabled = 1
                    next_run = self._next_run(
                        task["schedule_type"],
                        task["schedule_value"],
                        now,
                    )

                db.execute(
                    """
                    UPDATE scheduled_tasks
                    SET enabled = ?, next_run_at = ?, last_run_at = ?, last_error = NULL
                    WHERE id = ?
                    """,
                    (enabled, next_run, now, task["id"]),
                )
                claimed.append(task)
            db.commit()
        return claimed

    def _execute(self, task: dict[str, Any]) -> None:
        try:
            self.callback(task)
        except Exception as exc:
            with self._lock, self._connect() as db:
                db.execute(
                    "UPDATE scheduled_tasks SET last_error = ? WHERE id = ?",
                    (str(exc)[:2000], task["id"]),
                )
                db.commit()

    def _loop(self) -> None:
        while not self._stop.wait(self.poll_seconds):
            try:
                due = self._claim_due()
            except Exception:
                continue

            for task in due:
                threading.Thread(
                    target=self._execute,
                    args=(task,),
                    name=f"jarvis-task-{task['id']}",
                    daemon=True,
                ).start()
