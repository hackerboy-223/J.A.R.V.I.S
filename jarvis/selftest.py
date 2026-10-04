from __future__ import annotations

import json
from pathlib import Path
import tempfile


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

    def api_check() -> str:
        from jarvis.api import create_app
        assert callable(create_app)
        return "FastAPI module/import OK"

    def permissions_check() -> str:
        from jarvis.core.permissions import PermissionEngine
        with tempfile.TemporaryDirectory() as tmp:
            engine = PermissionEngine(Path(tmp) / "permissions.db")
            assert engine.get("screen.read").decision.value == "ask"
            engine.set("screen.read", "deny")
            assert engine.get("screen.read").decision.value == "deny"
        return "allow/ask/deny persistence OK"

    def events_check() -> str:
        from jarvis.core.events import EventBus
        bus = EventBus()
        seen = []
        token = bus.subscribe(seen.append)
        bus.publish("selftest", {"ok": True})
        bus.unsubscribe(token)
        assert seen and seen[0].payload["ok"] is True
        return "publish/subscribe/history OK"

    def jobs_check() -> str:
        from jarvis.core.events import EventBus
        from jarvis.core.jobs import JobManager
        import time
        manager = JobManager(EventBus(), max_workers=1)
        try:
            job_id = manager.submit("selftest", lambda ctx: "done")
            deadline = time.time() + 2
            while time.time() < deadline:
                item = manager.get(job_id)
                if item and item["state"] == "completed":
                    break
                time.sleep(0.02)
            assert manager.get(job_id)["state"] == "completed"
        finally:
            manager.shutdown()
        return "background job lifecycle OK"

    def platform_store_check() -> str:
        from jarvis.core.platform_store import PlatformStore
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"
            root.mkdir()
            store = PlatformStore(Path(tmp) / "platform.db")
            workspace = store.add_workspace("demo", str(root), favorite=True)
            mission = store.create_mission("demo mission", workspace["id"], "operative")
            store.checkpoint(mission["id"], {"step": 1})
            assert store.latest_checkpoint(mission["id"])["state"]["step"] == 1
        return "workspace/mission/checkpoint persistence OK"

    def undo_check() -> str:
        from jarvis.core.undo import UndoManager
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.txt"
            path.write_text("before", encoding="utf-8")
            manager = UndoManager()
            path.write_text("after", encoding="utf-8")
            undo_id = manager.record(path, "before", "after")
            manager.undo(undo_id)
            assert path.read_text(encoding="utf-8") == "before"
        return "reversible file snapshots OK"

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
    check("Platform store", platform_store_check)
    check("Undo", undo_check)

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
