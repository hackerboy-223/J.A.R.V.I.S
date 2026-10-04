from __future__ import annotations

from pathlib import Path

from jarvis.core.activity import ActivityStore
from jarvis.core.changes import ChangeJournal
from jarvis.core.events import EventBus
from jarvis.core.file_index import FileIndex
from jarvis.core.jobs import JobManager
from jarvis.core.missions import MissionStore
from jarvis.core.permissions import PermissionEngine
from jarvis.core.recent import RecentFileStore
from jarvis.core.workspaces import WorkspaceStore


class JarvisRuntime:
    """Shared operational services for desktop, API and tools."""

    def __init__(self, db_path: Path) -> None:
        self.events = EventBus()
        self.activity = ActivityStore(db_path)
        self.permissions = PermissionEngine(db_path)
        self.jobs = JobManager(db_path, self.events, self.activity)
        self.workspaces = WorkspaceStore(db_path)
        self.missions = MissionStore(db_path)
        self.recent_files = RecentFileStore(db_path)
        self.file_index = FileIndex(db_path)
        self.changes = ChangeJournal(db_path)

    def stop_all(self) -> int:
        count = self.jobs.cancel_all()
        self.events.emit("runtime.stop_all", {"cancelled_jobs": count})
        self.activity.log(
            "runtime",
            "stop_all",
            status="requested",
            summary=f"{count} job(s) cancellation requested",
        )
        return count
