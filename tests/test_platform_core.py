from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from jarvis.core.events import EventBus
from jarvis.core.jobs import JobManager
from jarvis.core.permissions import PermissionDecision, PermissionEngine
from jarvis.core.platform_store import PlatformStore


class PlatformCoreTests(unittest.TestCase):
    def test_event_bus_delivers_and_keeps_history(self) -> None:
        bus = EventBus(history_limit=20)
        received = []
        token = bus.subscribe(received.append)
        event = bus.publish("demo.event", {"value": 42})
        bus.unsubscribe(token)
        self.assertEqual(received[0].id, event.id)
        self.assertEqual(bus.recent(1)[0]["payload"]["value"], 42)

    def test_permissions_persist_and_session_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "platform.db"
            permissions = PermissionEngine(db)
            self.assertEqual(
                permissions.get("screen.read").decision,
                PermissionDecision.ASK,
            )
            permissions.set("screen.read", "deny", scope="always")
            self.assertEqual(permissions.get("screen.read").decision, PermissionDecision.DENY)
            permissions.set("screen.read", "allow", scope="session")
            self.assertEqual(permissions.get("screen.read").decision, PermissionDecision.ALLOW)
            permissions.clear_session()
            self.assertEqual(permissions.get("screen.read").decision, PermissionDecision.DENY)

    def test_job_manager_completes_job(self) -> None:
        bus = EventBus()
        jobs = JobManager(bus, max_workers=1)
        try:
            job_id = jobs.submit("demo", lambda ctx: "done")
            deadline = time.time() + 3
            while time.time() < deadline:
                item = jobs.get(job_id)
                if item and item["state"] in {"completed", "failed"}:
                    break
                time.sleep(0.02)
            item = jobs.get(job_id)
            self.assertIsNotNone(item)
            self.assertEqual(item["state"], "completed")
            self.assertEqual(item["result"], "done")
        finally:
            jobs.shutdown()

    def test_job_manager_cooperative_cancel(self) -> None:
        bus = EventBus()
        jobs = JobManager(bus, max_workers=1)
        started = threading.Event()

        def worker(ctx):
            started.set()
            while True:
                ctx.checkpoint()
                time.sleep(0.01)

        try:
            job_id = jobs.submit("cancel-demo", worker)
            self.assertTrue(started.wait(1))
            self.assertTrue(jobs.cancel(job_id))
            deadline = time.time() + 2
            while time.time() < deadline:
                item = jobs.get(job_id)
                if item and item["state"] == "cancelled":
                    break
                time.sleep(0.02)
            self.assertEqual(jobs.get(job_id)["state"], "cancelled")
        finally:
            jobs.shutdown()

    def test_platform_store_workspaces_missions_and_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "platform.db"
            root = Path(temp_dir) / "workspace"
            root.mkdir()
            store = PlatformStore(db)
            workspace = store.add_workspace("Demo", str(root), favorite=True)
            mission = store.create_mission("Audit", workspace["id"], "operative")
            store.checkpoint(mission["id"], {"step": 3})
            checkpoint = store.latest_checkpoint(mission["id"])
            self.assertEqual(checkpoint["state"]["step"], 3)
            self.assertEqual(store.workspaces()[0]["favorite"], 1)


if __name__ == "__main__":
    unittest.main()
