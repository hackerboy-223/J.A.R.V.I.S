from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import json
import sqlite3
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable

from jarvis.core.activity import ActivityStore
from jarvis.core.events import EventBus


class JobCancelled(RuntimeError):
    pass


@dataclass
class JobContext:
    id: str
    cancel_event: threading.Event
    _progress: Callable[[float | None, str], None]

    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def checkpoint(self) -> None:
        if self.cancelled():
            raise JobCancelled("Job annulé.")

    def progress(self, value: float | None = None, message: str = "") -> None:
        self.checkpoint()
        self._progress(value, message)


JobRunner = Callable[[JobContext], Any]


class JobManager:
    """Persistent cooperative job lifecycle manager."""

    def __init__(self, db_path: Path, events: EventBus, activity: ActivityStore) -> None:
        self.db_path = db_path
        self.events = events
        self.activity = activity
        self._lock = threading.RLock()
        self._cancellations: dict[str, threading.Event] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._init_db()
        self._recover_interrupted()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _init_db(self) -> None:
        with self._lock, closing(self._connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_jobs (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL,
                    message TEXT,
                    metadata_json TEXT,
                    result_json TEXT,
                    error TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    started_at DATETIME,
                    finished_at DATETIME
                );
                CREATE INDEX IF NOT EXISTS idx_runtime_jobs_recent
                ON runtime_jobs(created_at DESC);
                """
            )
            db.commit()

    def _recover_interrupted(self) -> None:
        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                UPDATE runtime_jobs
                SET status='failed',
                    error='Application stopped before the job completed.',
                    finished_at=CURRENT_TIMESTAMP
                WHERE status IN ('queued','running','waiting_permission','cancelling')
                """
            )
            db.commit()

    def _update(self, job_id: str, **values: Any) -> None:
        allowed = {
            "status", "progress", "message", "result_json", "error",
            "started_at", "finished_at",
        }
        clean = {key: value for key, value in values.items() if key in allowed}
        if not clean:
            return
        clause = ", ".join(f"{key}=?" for key in clean)
        with self._lock, closing(self._connect()) as db:
            db.execute(
                f"UPDATE runtime_jobs SET {clause} WHERE id=?",
                (*clean.values(), job_id),
            )
            db.commit()

    def submit(
        self,
        label: str,
        runner: JobRunner,
        *,
        kind: str = "agent",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        job_id = uuid.uuid4().hex[:16]
        cancel_event = threading.Event()
        with self._lock, closing(self._connect()) as db:
            db.execute(
                """
                INSERT INTO runtime_jobs(id, label, kind, status, metadata_json)
                VALUES (?, ?, ?, 'queued', ?)
                """,
                (
                    job_id,
                    label[:240],
                    kind[:80],
                    json.dumps(metadata or {}, ensure_ascii=False, default=str)[:30000],
                ),
            )
            db.commit()
        with self._lock:
            self._cancellations[job_id] = cancel_event

        thread = threading.Thread(
            target=self._run,
            args=(job_id, runner, cancel_event),
            name=f"jarvis-job-{job_id}",
            daemon=True,
        )
        with self._lock:
            self._threads[job_id] = thread
        self.events.emit("job.queued", {"job_id": job_id, "label": label, "kind": kind})
        thread.start()
        return job_id

    def _run(self, job_id: str, runner: JobRunner, cancel_event: threading.Event) -> None:
        with self._lock, closing(self._connect()) as db:
            db.execute(
                "UPDATE runtime_jobs SET status='running', started_at=CURRENT_TIMESTAMP WHERE id=?",
                (job_id,),
            )
            db.commit()
        self.events.emit("job.started", {"job_id": job_id})

        def report(value: float | None, message: str) -> None:
            normalized = None if value is None else max(0.0, min(1.0, float(value)))
            self._update(job_id, progress=normalized, message=message[:2000])
            self.events.emit(
                "job.progress",
                {"job_id": job_id, "progress": normalized, "message": message},
            )

        ctx = JobContext(job_id, cancel_event, report)
        try:
            ctx.checkpoint()
            result = runner(ctx)
            ctx.checkpoint()
            payload = json.dumps(result, ensure_ascii=False, default=str)[:60000]
            with self._lock, closing(self._connect()) as db:
                db.execute(
                    """
                    UPDATE runtime_jobs
                    SET status='completed', progress=1.0, result_json=?,
                        finished_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (payload, job_id),
                )
                db.commit()
            self.activity.log("job", "completed", summary=job_id)
            self.events.emit("job.completed", {"job_id": job_id, "result": result})
        except JobCancelled as exc:
            with self._lock, closing(self._connect()) as db:
                db.execute(
                    """
                    UPDATE runtime_jobs
                    SET status='cancelled', error=?, finished_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (str(exc), job_id),
                )
                db.commit()
            self.activity.log("job", "cancelled", status="cancelled", summary=job_id)
            self.events.emit("job.cancelled", {"job_id": job_id})
        except Exception as exc:
            detail = traceback.format_exc(limit=12)
            with self._lock, closing(self._connect()) as db:
                db.execute(
                    """
                    UPDATE runtime_jobs
                    SET status='failed', error=?, finished_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (f"{type(exc).__name__}: {exc}", job_id),
                )
                db.commit()
            self.activity.log(
                "job", "failed", status="error", summary=str(exc),
                details={"job_id": job_id, "traceback": detail},
            )
            self.events.emit("job.failed", {"job_id": job_id, "error": str(exc)})
        finally:
            with self._lock:
                self._cancellations.pop(job_id, None)
                self._threads.pop(job_id, None)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            event = self._cancellations.get(job_id)
        if event is None:
            return False
        self._update(job_id, status="cancelling", message="Annulation demandée")
        event.set()
        self.events.emit("job.cancelling", {"job_id": job_id})
        return True

    def cancel_all(self) -> int:
        with self._lock:
            ids = list(self._cancellations)
        return sum(1 for job_id in ids if self.cancel(job_id))

    def wait(self, job_id: str, timeout: float | None = None) -> dict[str, Any] | None:
        with self._lock:
            thread = self._threads.get(job_id)
        if thread is not None:
            thread.join(timeout=timeout)
        return self.get(job_id)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock, closing(self._connect()) as db:
            row = db.execute("SELECT * FROM runtime_jobs WHERE id=?", (job_id,)).fetchone()
        return self._decode(dict(row)) if row is not None else None

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM runtime_jobs ORDER BY created_at DESC LIMIT ?",
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        return [self._decode(dict(row)) for row in rows]

    @staticmethod
    def _decode(item: dict[str, Any]) -> dict[str, Any]:
        for source, target in (("metadata_json", "metadata"), ("result_json", "result")):
            raw = item.pop(source, None)
            try:
                item[target] = json.loads(str(raw)) if raw else None
            except json.JSONDecodeError:
                item[target] = None
        return item
