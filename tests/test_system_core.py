from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest

from jarvis.core.activity import ActivityStore
from jarvis.core.events import EventBus
from jarvis.core.file_index import FileIndex
from jarvis.core.jobs import JobManager
from jarvis.core.missions import MissionStore
from jarvis.core.permissions import PermissionEngine
from jarvis.core.workspaces import WorkspaceStore


class PermissionEngineTests(unittest.TestCase):
    def test_rules_and_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = PermissionEngine(Path(tmp) / "test.db")
            self.assertEqual(engine.get("system.read"), "allow")
            self.assertTrue(engine.authorize("system.read", "read"))
            self.assertFalse(engine.authorize("screen.capture", "capture", lambda _: False))
            engine.set("screen.capture", "allow", "session")
            self.assertTrue(engine.authorize("screen.capture", "capture"))


class EventBusTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        bus = EventBus()
        with bus.subscribe() as subscription:
            emitted = bus.emit("demo", {"n": 3})
            received = subscription.get(timeout=1)
            self.assertEqual(received.id, emitted.id)
            self.assertEqual(received.payload["n"], 3)


class JobManagerTests(unittest.TestCase):
    def test_job_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "jobs.db"
            bus = EventBus()
            activity = ActivityStore(db)
            jobs = JobManager(db, bus, activity)
            job_id = jobs.submit("demo", lambda ctx: {"ok": True})

            deadline = time.time() + 3
            while time.time() < deadline:
                job = jobs.get(job_id)
                if job and job["status"] in {"completed", "failed", "cancelled"}:
                    break
                time.sleep(0.02)

            job = jobs.get(job_id)
            self.assertIsNotNone(job)
            self.assertEqual(job["status"], "completed")
            self.assertEqual(job["result"], {"ok": True})

    def test_job_cancellation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "jobs.db"
            jobs = JobManager(db, EventBus(), ActivityStore(db))

            def runner(ctx):
                for _ in range(200):
                    time.sleep(0.005)
                    ctx.checkpoint()
                return "late"

            job_id = jobs.submit("cancel", runner)
            self.assertTrue(jobs.cancel(job_id))

            deadline = time.time() + 3
            while time.time() < deadline:
                job = jobs.get(job_id)
                if job and job["status"] in {"cancelled", "failed", "completed"}:
                    break
                time.sleep(0.02)

            self.assertEqual(jobs.get(job_id)["status"], "cancelled")


class WorkspaceIndexTests(unittest.TestCase):
    def test_workspace_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            (root / "jarvis-architecture.md").write_text("demo", encoding="utf-8")
            db = Path(tmp) / "core.db"

            workspaces = WorkspaceStore(db)
            workspace = workspaces.add("JARVIS", root, favorite=True)
            index = FileIndex(db)
            result = index.index_workspace(workspace["id"], root)
            self.assertEqual(result["indexed"], 1)

            matches = index.search("architecture", workspace_id=workspace["id"])
            self.assertEqual(matches[0]["name"], "jarvis-architecture.md")

            missions = MissionStore(db)
            mission = missions.create("Deep work", workspace_id=workspace["id"])
            self.assertTrue(mission["operator_id"].startswith("mission:"))


if __name__ == "__main__":
    unittest.main()
