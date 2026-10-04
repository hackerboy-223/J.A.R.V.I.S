from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import queue
import threading
import uuid
from typing import Any


@dataclass(frozen=True)
class RuntimeEvent:
    id: str
    type: str
    payload: dict[str, Any]
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventSubscription:
    def __init__(self, bus: "EventBus", token: str, events: "queue.Queue[RuntimeEvent]") -> None:
        self._bus = bus
        self.token = token
        self.events = events
        self._closed = False

    def get(self, timeout: float | None = None) -> RuntimeEvent:
        return self.events.get(timeout=timeout)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._bus.unsubscribe(self.token)

    def __enter__(self) -> "EventSubscription":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class EventBus:
    """Thread-safe in-process event bus used by desktop UI and FastAPI transports."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: dict[str, queue.Queue[RuntimeEvent]] = {}

    def subscribe(self, *, maxsize: int = 256) -> EventSubscription:
        token = uuid.uuid4().hex
        events: queue.Queue[RuntimeEvent] = queue.Queue(maxsize=max(8, maxsize))
        with self._lock:
            self._subscribers[token] = events
        return EventSubscription(self, token, events)

    def unsubscribe(self, token: str) -> None:
        with self._lock:
            self._subscribers.pop(token, None)

    def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> RuntimeEvent:
        event = RuntimeEvent(
            id=uuid.uuid4().hex,
            type=str(event_type or "event"),
            payload=dict(payload or {}),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            queues = list(self._subscribers.values())

        for target in queues:
            try:
                target.put_nowait(event)
            except queue.Full:
                try:
                    target.get_nowait()
                    target.put_nowait(event)
                except (queue.Empty, queue.Full):
                    pass
        return event
