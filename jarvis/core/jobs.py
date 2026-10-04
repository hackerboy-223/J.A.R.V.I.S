from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
import threading
import uuid
from typing import Any, Callable

from jarvis.core.events import EventBus


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_PERMISSION = "waiting_permission"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    title: str
    state: JobState
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    progress: float = 0.0
    error: str | None = None
    result: Any = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.value
        return value


class JobContext:
    def __init__(self, manager: "JobManager", job_id: str, cancel_event: threading.Event) -> None:
        self.manager = manager
        self.job_id = job_id
        self.cancel_event = cancel_event

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def checkpoint(self) -> None:
        if self.cancelled:
            raise InterruptedError("Job cancelled")

    def progress(self, value: float, message: str | None = None) -> None:
        self.manager._set_progress(self.job_id, value, message)


JobFn = Callable[[JobContext], Any]


class JobManager:
    """Cooperative background jobs with observable state and global cancellation."""

    def __init__(self, event_bus: EventBus, max_workers: int = 4) -> None:
        self.event_bus = event_bus
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="jarvis-job",
        )
        self._lock = threading.RLock()
        self._jobs: dict[str, Job] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._futures: dict[str, Future[Any]] = {}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def submit(self, title: str, fn: JobFn) -> str:
        job_id = uuid.uuid4().hex[:16]
        job = Job(job_id, title.strip() or "JARVIS job", JobState.QUEUED, self._now())
        cancel_event = threading.Event()
        with self._lock:
            self._jobs[job_id] = job
            self._cancel[job_id] = cancel_event
        self.event_bus.publish("job.queued", job.to_dict())

        def runner() -> Any:
            self._transition(job_id, JobState.RUNNING, started=True)
            ctx = JobContext(self, job_id, cancel_event)
            try:
                ctx.checkpoint()
                result = fn(ctx)
                if cancel_event.is_set():
                    self._transition(job_id, JobState.CANCELLED, finished=True)
                    return None
                with self._lock:
                    self._jobs[job_id].result = result
                    self._jobs[job_id].progress = 1.0
                self._transition(job_id, JobState.COMPLETED, finished=True)
                return result
            except InterruptedError:
                self._transition(job_id, JobState.CANCELLED, finished=True)
                return None
            except Exception as exc:
                with self._lock:
                    self._jobs[job_id].error = str(exc)
                self._transition(job_id, JobState.FAILED, finished=True)
                raise

        future = self._executor.submit(runner)
        with self._lock:
            self._futures[job_id] = future
        return job_id

    def _transition(
        self,
        job_id: str,
        state: JobState,
        *,
        started: bool = False,
        finished: bool = False,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.state = state
            if started:
                job.started_at = self._now()
            if finished:
                job.finished_at = self._now()
            snapshot = job.to_dict()
        self.event_bus.publish(f"job.{state.value}", snapshot)

    def _set_progress(self, job_id: str, value: float, message: str | None = None) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.progress = max(0.0, min(1.0, float(value)))
            snapshot = job.to_dict()
        if message:
            snapshot["message"] = message
        self.event_bus.publish("job.progress", snapshot)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            event = self._cancel.get(job_id)
            job = self._jobs.get(job_id)
            if event is None or job is None:
                return False
            if job.state in {JobState.COMPLETED, JobState.CANCELLED, JobState.FAILED}:
                return False
            event.set()
            job.state = JobState.CANCELLING
            snapshot = job.to_dict()
        self.event_bus.publish("job.cancelling", snapshot)
        return True

    def cancel_all(self) -> int:
        with self._lock:
            ids = list(self._jobs)
        return sum(1 for job_id in ids if self.cancel(job_id))

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return None if job is None else job.to_dict()

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            jobs = list(self._jobs.values())[-max(1, min(int(limit), 500)):]
        return [job.to_dict() for job in reversed(jobs)]

    def shutdown(self) -> None:
        self.cancel_all()
        self._executor.shutdown(wait=False, cancel_futures=True)
