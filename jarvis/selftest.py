from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time


def run() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, fn) -> None:
        try:
            detail = fn()
            checks.append((name, True, str(detail or "OK")))
        except Exception as exc:
            checks.append((name, False, f"{type(exc).__name__}: {exc}"))

    def scheduler_check() -> str:
        from jarvis.core.scheduler import TaskScheduler
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            scheduler = TaskScheduler(db, callback=lambda _: None)
            task = scheduler.create("test", "interval", "60", "operative")
            assert task["enabled"] == 1
            assert scheduler.list()
            scheduler.pause(task["id"])
            scheduler.resume(task["id"])
            scheduler.cancel(task["id"])
            scheduler.stop()
        return "once/interval/cron engine import + SQLite CRUD OK"

    def operative_check() -> str:
        from jarvis.core.memory import MemoryStore
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.db")
            store.set_operative_state("selftest", {"step": 2})
            assert store.get_operative_state("selftest")["step"] == 2
            store.add_operative_run("selftest", "hello", "world")
            assert store.recent_operative_runs("selftest")
        return "persistent state/history OK"

    def knowledge_check() -> str:
        from jarvis.knowledge import KnowledgeBase
        with tempfile.TemporaryDirectory() as tmp:
            kb = KnowledgeBase(Path(tmp) / "knowledge.db")

            class _OfflineEmbeddings:
                enabled = False

            kb.embedding_client = _OfflineEmbeddings()
            kb.add_text(
                "demo.txt",
                "Python est un langage de programmation. "
                "JARVIS utilise une base de connaissances locale pour retrouver des informations.",
            )
            results = kb.search("langage Python", top_k=3)
            assert results and results[0]["document"] == "demo.txt"
        return "BM25 fallback OK"

    def skills_check() -> str:
        from jarvis.core.skills import SkillManager
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            directory = root / "demo"
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(
                "# Demo skill\n\nUse this skill only for the self-test.",
                encoding="utf-8",
            )
            manager = SkillManager(root)
            assert manager.list()[0]["name"] == "demo"
            loaded = manager.load("demo")
            assert "self-test" in loaded["instructions"]
        return "discovery/load OK"

    def sandbox_check() -> str:
        from jarvis.tools.sandbox import python_sandbox
        result = python_sandbox(
            {
                "code": "import math\nprint(math.sqrt(81))",
                "timeout_seconds": 3,
            }
        )
        assert result["returncode"] == 0
        assert "9.0" in result["stdout"]
        return "restricted Python subprocess OK"

    def mcp_check() -> str:
        from jarvis.core.mcp_bridge import MCPManager
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "mcp.json"
            config.write_text(json.dumps({"servers": {}}), encoding="utf-8")
            manager = MCPManager(config)
            assert manager.list_servers() == []
        return "MCP config/parser OK"

    def permissions_check() -> str:
        from jarvis.core.permissions import PermissionEngine
        with tempfile.TemporaryDirectory() as tmp:
            engine = PermissionEngine(Path(tmp) / "permissions.db")
            assert engine.get("system.read") == "allow"
            engine.set("screen.capture", "deny", "session")
            assert engine.get("screen.capture") == "deny"
            assert not engine.authorize("screen.capture", "test", lambda _: True)
        return "ALLOW/ASK/DENY + scopes OK"

    def events_check() -> str:
        from jarvis.core.events import EventBus
        bus = EventBus()
        with bus.subscribe() as subscription:
            emitted = bus.emit("selftest.event", {"value": 7})
            received = subscription.get(timeout=1)
            assert received.id == emitted.id
            assert received.payload["value"] == 7
        return "thread-safe publish/subscribe OK"

    def jobs_check() -> str:
        from jarvis.core.activity import ActivityStore
        from jarvis.core.events import EventBus
        from jarvis.core.jobs import JobManager
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "jobs.db"
            events = EventBus()
            activity = ActivityStore(db)
            jobs = JobManager(db, events, activity)
            job_id = jobs.submit("selftest", lambda ctx: {"value": 42})
            deadline = time.time() + 3
            while time.time() < deadline:
                item = jobs.get(job_id)
                if item and item["status"] in {"completed", "failed", "cancelled"}:
                    break
                time.sleep(0.02)
            item = jobs.get(job_id)
            assert item and item["status"] == "completed"
            assert item["result"]["value"] == 42
        return "queued/running/completed persistence OK"

    def file_index_check() -> str:
        from jarvis.core.file_index import FileIndex
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"
            root.mkdir()
            (root / "important-notes.md").write_text("demo", encoding="utf-8")
            index = FileIndex(Path(tmp) / "index.db")
            result = index.index_workspace("demo", root)
            assert result["indexed"] == 1
            matches = index.search("important", workspace_id="demo")
            assert matches and matches[0]["name"] == "important-notes.md"
        return "SQLite FTS5 workspace search OK"

    def mission_workspace_check() -> str:
        from jarvis.core.missions import MissionStore
        from jarvis.core.workspaces import WorkspaceStore
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"
            root.mkdir()
            db = Path(tmp) / "mission.db"
            workspaces = WorkspaceStore(db)
            workspace = workspaces.add("Demo", root, True)
            missions = MissionStore(db)
            mission = missions.create("Continue demo", workspace_id=workspace["id"])
            assert mission["operator_id"].startswith("mission:")
            assert missions.get(mission["id"])["title"] == "Continue demo"
        return "persistent workspaces/missions OK"

    def api_check() -> str:
        from jarvis.api import create_app
        assert callable(create_app)
        return "FastAPI module/import OK"

    check("Scheduler", scheduler_check)
    check("Operative state", operative_check)
    check("Knowledge memory", knowledge_check)
    check("Skills", skills_check)
    check("Python sandbox", sandbox_check)
    check("MCP", mcp_check)
    check("FastAPI", api_check)
    check("Permissions", permissions_check)
    check("Event bus", events_check)
    check("Job manager", jobs_check)
    check("File index", file_index_check)
    check("Missions/workspaces", mission_workspace_check)

    print("\nJ.A.R.V.I.S. PLATFORM SELF-TEST")
    print("=" * 42)
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    failures = [item for item in checks if not item[1]]
    print("=" * 42)
    print(f"{len(checks) - len(failures)}/{len(checks)} checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
