from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import threading
import uuid
from typing import Any, Callable


@dataclass(frozen=True)
class Event:
    id: str
    type: str
    payload: dict[str, Any]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


Subscriber = Callable[[Event], None]


class EventBus:
    """Small in-process event bus used by UI, API and platform services."""

    def __init__(self, history_limit: int = 300) -> None:
        self._lock = threading.RLock()
        self._subscribers: dict[str, Subscriber] = {}
        self._history: list[Event] = []
        self._history_limit = max(20, int(history_limit))

    def subscribe(self, callback: Subscriber) -> str:
        token = uuid.uuid4().hex
        with self._lock:
            self._subscribers[token] = callback
        return token

    def unsubscribe(self, token: str) -> None:
        with self._lock:
            self._subscribers.pop(token, None)

    def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> Event:
        event = Event(
            id=uuid.uuid4().hex,
            type=str(event_type).strip() or "event",
            payload=dict(payload or {}),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._history.append(event)
            self._history = self._history[-self._history_limit :]
            subscribers = list(self._subscribers.values())
        for callback in subscribers:
            try:
                callback(event)
            except Exception:
                continue
        return event

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._history[-max(1, min(int(limit), self._history_limit)):])
        return [item.to_dict() for item in items]
